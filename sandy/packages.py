"""Sandy's package system: a project manifest, dependency resolution, and a
lockfile — the machinery that lets developers share and reuse code.

A project has a manifest, `sandy.toml`:

    [package]
    name = "myapp"
    version = "0.1.0"

    [dependencies]
    geometry = { path = "../geometry" }   # a local path dependency
    utils = "./vendor/utils"              # string shorthand for { path = ... }
    webby = { git = "https://example.com/webby.sy.git", rev = "main" }

`sandy install` resolves every dependency to a directory (path deps are used in
place; git deps are cloned into `sandy_modules/`), verifies each one exposes an
importable module, and writes `sandy.lock` recording what was resolved. At run
time `import "geometry"` then resolves through the lock, so a program sees its
dependencies by bare name — exactly like the bundled standard library.

A package directory is itself a project (it has a `sandy.toml`); its importable
module is `<dir>/<name>.sy` or `<dir>/src/<name>.sy`, and submodules are
imported as `import "<name>/<sub>"`.
"""

import json
import os
import re
import shutil
import subprocess
import tomllib

MANIFEST = "sandy.toml"
LOCKFILE = "sandy.lock"
MODULES_DIR = "sandy_modules"
REGISTRY_ENV = "SANDY_REGISTRY"


class PackageError(Exception):
    """A problem with a manifest, lockfile, or dependency resolution."""


# -- semantic versions ----------------------------------------------------

_VERSIONISH = re.compile(r"^\s*(\*|[\^~><=]|\d)")


def _looks_like_version(s):
    """Whether a bare dependency string is a version/constraint (vs a path)."""
    return bool(_VERSIONISH.match(s))


def parse_version(v):
    """('1.2.3') -> (1, 2, 3). Extra/missing parts are tolerated."""
    core = v.strip().lstrip("v").split("-", 1)[0].split("+", 1)[0]
    parts = (core.split(".") + ["0", "0", "0"])[:3]
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        raise PackageError(f"not a valid version: {v!r}")


def satisfies(version, constraint):
    """Whether `version` satisfies a constraint: exact, *, ^, ~, or a
    comparator (>=, >, <=, <, =), possibly comma-separated (an AND)."""
    c = constraint.strip()
    if c in ("", "*"):
        return True
    if "," in c:
        return all(satisfies(version, part) for part in c.split(","))
    v = parse_version(version)
    if c[0] == "^":                       # compatible-with: same left-most nonzero
        base = parse_version(c[1:])
        if base[0] > 0:
            upper = (base[0] + 1, 0, 0)
        elif base[1] > 0:
            upper = (0, base[1] + 1, 0)
        else:
            upper = (0, 0, base[2] + 1)
        return base <= v < upper
    if c[0] == "~":                       # same major.minor, >= patch
        base = parse_version(c[1:])
        return base <= v < (base[0], base[1] + 1, 0)
    for op in (">=", "<=", ">", "<", "="):
        if c.startswith(op):
            other = parse_version(c[len(op):])
            if op == ">=":
                return v >= other
            if op == "<=":
                return v <= other
            if op == ">":
                return v > other
            if op == "<":
                return v < other
            return v == other
    return v == parse_version(c)          # bare version is exact


# -- registry (a directory of <name>/<version>/ package trees) ------------

def _is_url(location):
    return isinstance(location, str) and location.startswith(("http://", "https://"))


def registry_dir(explicit=None):
    """The registry location: an explicit value, else $SANDY_REGISTRY, else
    ~/.sandy/registry. A URL is returned as-is; a path is made absolute."""
    loc = explicit or os.environ.get(REGISTRY_ENV) \
        or os.path.join(os.path.expanduser("~"), ".sandy", "registry")
    return loc if _is_url(loc) else os.path.abspath(loc)


_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _safe_name(name):
    if not _NAME_OK.match(name) or ".." in name:
        raise PackageError(f"unsafe package name/version: {name!r}")
    return name


def _collect_files(root):
    """{relative path: text content} of a project tree, skipping build/VCS
    dirs and any file that isn't UTF-8 text (packages are source)."""
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _PUBLISH_SKIP]
        for fn in filenames:
            if fn in _PUBLISH_SKIP:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                with open(full, encoding="utf-8") as f:
                    files[rel] = f.read()
            except (OSError, UnicodeDecodeError):
                continue
    return files


def _write_files(dest, files):
    """Write {relpath: content} under dest, rejecting path escapes."""
    base = os.path.abspath(dest)
    for rel, content in files.items():
        if rel.startswith("/") or ".." in rel.split("/"):
            raise PackageError(f"unsafe path in package: {rel!r}")
        target = os.path.join(base, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)


class _FileBackend:
    """A registry stored as a directory of <name>/<version>/ package trees."""

    def __init__(self, path):
        self.path = path

    def list_versions(self, name):
        root = os.path.join(self.path, name)
        if not os.path.isdir(root):
            return []
        vs = [d for d in os.listdir(root)
              if os.path.isdir(os.path.join(root, d))]
        return sorted(vs, key=parse_version)

    def has(self, name, version):
        return os.path.isdir(os.path.join(self.path, name, version))

    def read_files(self, name, version):
        return _collect_files(os.path.join(self.path, name, version))

    def publish(self, name, version, files, force):
        dest = os.path.join(self.path, _safe_name(name), _safe_name(version))
        if os.path.isdir(dest):
            if not force:
                raise PackageError(f"{name} {version} is already published")
            shutil.rmtree(dest)
        _write_files(dest, files)
        return dest


class _HttpBackend:
    """A registry served over HTTP (see sandy/registry_server.py)."""

    def __init__(self, base):
        self.base = base.rstrip("/")

    def _get(self, path):
        import urllib.request
        import urllib.error
        try:
            with urllib.request.urlopen(self.base + path, timeout=30) as r:
                return json.loads(r.read().decode("utf-8")), 200
        except urllib.error.HTTPError as e:
            return None, e.code
        except (urllib.error.URLError, OSError) as e:
            raise PackageError(f"registry {self.base!r} is unreachable: {e}")

    def list_versions(self, name):
        data, status = self._get(f"/packages/{name}")
        if data is None:
            return []
        return sorted(data.get("versions", []), key=parse_version)

    def has(self, name, version):
        return version in self.list_versions(name)

    def read_files(self, name, version):
        data, status = self._get(f"/packages/{name}/{version}")
        if data is None:
            raise PackageError(f"{name} {version} not found in registry")
        return data["files"]

    def publish(self, name, version, files, force):
        import urllib.request
        import urllib.error
        body = json.dumps({"files": files}).encode("utf-8")
        url = f"{self.base}/packages/{name}/{version}"
        if force:
            url += "?force=1"
        req = urllib.request.Request(
            url, data=body, method="PUT",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
                return f"{self.base}/packages/{name}/{version}"
        except urllib.error.HTTPError as e:
            if e.code == 409:
                raise PackageError(f"{name} {version} is already published")
            raise PackageError(f"publish failed ({e.code})")
        except (urllib.error.URLError, OSError) as e:
            raise PackageError(f"registry {self.base!r} is unreachable: {e}")


def _backend(registry):
    return _HttpBackend(registry) if _is_url(registry) else _FileBackend(registry)


def available_versions(registry, name):
    """Sorted (ascending) list of versions published for `name`."""
    return _backend(registry).list_versions(name)


def resolve_version(registry, name, constraint):
    """The highest published version of `name` satisfying `constraint`."""
    versions = available_versions(registry, name)
    if not versions:
        raise PackageError(
            f"dependency '{name}': not found in registry {registry!r}")
    matches = [v for v in versions if satisfies(v, constraint)]
    if not matches:
        raise PackageError(
            f"dependency '{name}': no version matches '{constraint}' "
            f"(available: {', '.join(versions)})")
    return matches[-1]


# -- locating a project ----------------------------------------------------

def find_project_root(start_dir):
    """Walk up from `start_dir` to the nearest directory holding a manifest."""
    d = os.path.abspath(start_dir)
    while True:
        if os.path.exists(os.path.join(d, MANIFEST)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


# -- manifest --------------------------------------------------------------

def load_manifest(root):
    """Parse the manifest at `root`, or None if there is none."""
    path = os.path.join(root, MANIFEST)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise PackageError(f"{MANIFEST}: {e}")
    if not isinstance(data.get("package"), dict) or "name" not in data["package"]:
        raise PackageError(f"{MANIFEST}: a [package] table with a name is required")
    data.setdefault("dependencies", {})
    return data


def _dep_spec(value):
    """Normalize a dependency value to a dict. A bare string is a registry
    version constraint when it looks like one ("1.2.3", "^1.0", "*"), a git
    URL when it looks like one, otherwise a local path."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        if _looks_like_version(value):
            return {"version": value}
        if value.startswith(("http://", "https://", "git@", "git:")):
            return {"git": value[4:] if value.startswith("git:") else value}
        return {"path": value}
    raise PackageError(f"invalid dependency specification: {value!r}")


# -- resolving a package's importable module -------------------------------

def package_module(pkg_dir, module):
    """Absolute path of `module` inside package directory `pkg_dir`, or None.

    Looks for `<pkg_dir>/<module>.sy` and `<pkg_dir>/src/<module>.sy`."""
    rel = module if module.endswith(".sy") else module + ".sy"
    for candidate in (os.path.join(pkg_dir, rel),
                      os.path.join(pkg_dir, "src", rel)):
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return None


def _package_version(pkg_dir):
    """Best-effort version of the package at `pkg_dir` (from its manifest)."""
    try:
        m = load_manifest(pkg_dir)
        if m:
            return m["package"].get("version", "0.0.0")
    except PackageError:
        pass
    return "0.0.0"


# -- dependency resolution + install --------------------------------------

def resolve_dependencies(root, manifest, offline=False):
    """Resolve every dependency to an absolute directory. Path deps are used in
    place; git deps are cloned into `sandy_modules/` (skipped if already there,
    or if `offline`). Returns {name: {"source", "dir", "version"}}."""
    resolved = {}
    for name, value in manifest["dependencies"].items():
        spec = _dep_spec(value)
        if "path" in spec:
            pkg_dir = os.path.abspath(os.path.join(root, spec["path"]))
            if not os.path.isdir(pkg_dir):
                raise PackageError(
                    f"dependency '{name}': path '{spec['path']}' does not exist")
            resolved[name] = {"source": "path", "dir": pkg_dir,
                              "version": _package_version(pkg_dir)}
        elif "git" in spec:
            pkg_dir = os.path.join(root, MODULES_DIR, name)
            if not os.path.isdir(pkg_dir) and not offline:
                _git_clone(spec["git"], spec.get("rev"), pkg_dir, name)
            if not os.path.isdir(pkg_dir):
                raise PackageError(
                    f"dependency '{name}': not fetched (run `sandy install`)")
            resolved[name] = {"source": "git", "dir": os.path.abspath(pkg_dir),
                              "git": spec["git"], "version": _package_version(pkg_dir)}
        elif "version" in spec:
            registry = registry_dir()
            backend = _backend(registry)
            picked = resolve_version(registry, name, spec["version"])
            pkg_dir = os.path.join(root, MODULES_DIR, name)
            # (Re-)vendor if absent or a different version is present.
            already = _package_version(pkg_dir) if os.path.isdir(pkg_dir) else None
            if already != picked:
                if os.path.isdir(pkg_dir):
                    shutil.rmtree(pkg_dir)
                _write_files(pkg_dir, backend.read_files(name, picked))
            resolved[name] = {"source": "registry", "version": picked,
                              "constraint": spec["version"],
                              "dir": os.path.abspath(pkg_dir)}
        else:
            raise PackageError(
                f"dependency '{name}': needs a 'path', 'git', or 'version' "
                f"source")
        # Verify the package exposes an importable main module.
        if package_module(resolved[name]["dir"], name) is None:
            raise PackageError(
                f"dependency '{name}': no module '{name}.sy' found in "
                f"{resolved[name]['dir']} (expected {name}.sy or src/{name}.sy)")
    return resolved


def _git_clone(url, rev, target, name):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    cmd = ["git", "clone", "--depth", "1"]
    if rev:
        cmd += ["--branch", rev]
    cmd += [url, target]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as e:
        raise PackageError(f"dependency '{name}': git not available ({e})")
    if r.returncode != 0:
        raise PackageError(
            f"dependency '{name}': git clone failed:\n{r.stderr.strip()}")


def install(root):
    """Resolve dependencies and write the lockfile. Returns the resolved map."""
    manifest = load_manifest(root)
    if manifest is None:
        raise PackageError(f"no {MANIFEST} found in {root}")
    resolved = resolve_dependencies(root, manifest)
    write_lock(root, manifest, resolved)
    return resolved


def write_lock(root, manifest, resolved):
    lock = {"package": manifest["package"].get("name"),
            "packages": {name: {k: v for k, v in info.items()}
                         for name, info in sorted(resolved.items())}}
    with open(os.path.join(root, LOCKFILE), "w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write("\n")


def load_lock(root):
    """Return {name: dir} from the lockfile, or {} if there is none."""
    path = os.path.join(root, LOCKFILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {name: info["dir"]
            for name, info in data.get("packages", {}).items()
            if isinstance(info, dict) and "dir" in info}


# -- the import hook -------------------------------------------------------

def resolve_import(base_dir, path):
    """Resolve `import "<path>"` against installed packages, or None.

    `path` is a package name (`geometry`) or a package submodule
    (`geometry/shapes`). Resolution reads the lockfile at the project root; if
    the lock is missing, path dependencies from the manifest are still honored
    so `import` works during development before `sandy install` is run."""
    root = find_project_root(base_dir)
    if root is None:
        return None
    name = path[:-3] if path.endswith(".sy") else path
    head, _, rest = name.partition("/")
    pkg_dirs = load_lock(root)
    pkg_dir = pkg_dirs.get(head)
    if pkg_dir is None:
        pkg_dir = _dir_from_manifest(root, head)
    if pkg_dir is None or not os.path.isdir(pkg_dir):
        return None
    return package_module(pkg_dir, rest if rest else head)


def _dir_from_manifest(root, name):
    """Resolve a path dependency's directory straight from the manifest (used
    when there is no lockfile yet). Git deps require an install, so are skipped."""
    try:
        manifest = load_manifest(root)
    except PackageError:
        return None
    if not manifest or name not in manifest["dependencies"]:
        return None
    spec = _dep_spec(manifest["dependencies"][name])
    if "path" in spec:
        return os.path.abspath(os.path.join(root, spec["path"]))
    return None


# -- editing the manifest (`sandy add`) -----------------------------------

def add_dependency(root, name, spec):
    """Add or replace a dependency line in the manifest, creating it and/or the
    [dependencies] table if needed. `spec` is a path string or a git URL."""
    path = os.path.join(root, MANIFEST)
    line = _dep_line(name, spec)
    if not os.path.exists(path):
        base = os.path.basename(os.path.abspath(root)) or "app"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f'[package]\nname = "{base}"\nversion = "0.1.0"\n\n'
                    f"[dependencies]\n{line}\n")
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    out, in_deps, replaced, has_deps = [], False, False, False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_deps and not replaced:  # leaving [dependencies]; add here
                out.append(line); replaced = True
            in_deps = stripped == "[dependencies]"
            if in_deps:
                has_deps = True
        elif in_deps and stripped.startswith(f"{name} ") or \
                (in_deps and stripped.startswith(f"{name}=")):
            out.append(line); replaced = True; continue
        out.append(ln)
    if in_deps and not replaced:
        out.append(line); replaced = True
    if not has_deps:
        if out and out[-1].strip():
            out.append("")
        out += ["[dependencies]", line]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def _dep_line(name, spec):
    if _looks_like_version(spec):
        return f'{name} = "{spec}"'
    if spec.startswith(("http://", "https://", "git@", "git:")):
        url = spec[4:] if spec.startswith("git:") else spec
        return f'{name} = {{ git = "{url}" }}'
    return f'{name} = {{ path = "{spec}" }}'


# -- publishing to a registry ---------------------------------------------

_PUBLISH_SKIP = {MODULES_DIR, LOCKFILE, ".git", "__pycache__", ".sandy"}


def publish(root, registry=None, force=False):
    """Copy the project at `root` into the registry as <name>/<version>/.
    Versions are immutable: republishing an existing version fails unless
    `force`. Returns (name, version, destination)."""
    manifest = load_manifest(root)
    if manifest is None:
        raise PackageError(f"no {MANIFEST} to publish in {root}")
    name = manifest["package"]["name"]
    version = manifest["package"].get("version")
    if not version:
        raise PackageError(f"{MANIFEST}: [package] needs a version to publish")
    parse_version(version)                       # validate
    if package_module(root, name) is None:
        raise PackageError(
            f"nothing to publish: no module '{name}.sy' (or src/{name}.sy)")
    reg = registry_dir(registry)
    backend = _backend(reg)
    if backend.has(name, version) and not force:
        raise PackageError(
            f"{name} {version} is already published (versions are immutable; "
            f"bump the version or pass --force)")
    files = _collect_files(root)
    location = backend.publish(name, version, files, force)
    return name, version, location if location else reg

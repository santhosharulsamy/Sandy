# Sandy for VS Code

Syntax highlighting and editor configuration for the Sandy language (`.sy`).

## What it provides

- **Syntax highlighting** — keywords, strings (with `{interpolation}`),
  numbers, comments, function/struct definitions, type annotations, builtins,
  and operators (via `syntaxes/sandy.tmLanguage.json`).
- **Editor behavior** — line comments (`#`), bracket matching, auto-closing
  pairs, and brace-based auto-indentation (`language-configuration.json`).

## Installing (development)

Copy this folder into your VS Code extensions directory, then reload:

```bash
cp -r editors/vscode ~/.vscode/extensions/sandy-language-0.1.0
```

Or open this folder in VS Code and press **F5** to launch an Extension
Development Host.

## Live diagnostics, formatting, and completion

Highlighting is standalone. For live type-checking, formatting, completion,
and an outline, run Sandy's language server and point an LSP client at it:

```
command: sandy
args: ["lsp"]
```

See the [top-level editor notes](../README.md) and the project README's
*Editor support* section.

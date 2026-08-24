<!-- Thanks for contributing to Sandy! Please fill this in so reviewers can
     understand the change quickly. -->

## What does this change do?

<!-- A short description of the change and the motivation behind it. -->

## Type of change

- [ ] Bug fix
- [ ] New language feature or built-in
- [ ] Standard-library module
- [ ] Tooling (formatter, LSP, package manager, playground)
- [ ] Documentation
- [ ] Other

## Checklist

- [ ] `python -m unittest discover -s tests` passes locally.
- [ ] The interpreter and the VM still agree (equivalence tests pass).
- [ ] If I added a built-in, I updated all four places: `sandy/builtins.py`
      (implementation + `BUILTIN_NAMES`), the grammar in
      `editors/vscode/syntaxes/sandy.tmLanguage.json`, and the signatures in
      `sandy/lsp.py`.
- [ ] If I changed anything under `sandy/`, I regenerated the playground with
      `python web/build_playground.py`.
- [ ] I added or updated tests for the new behavior.
- [ ] I formatted my code to match the surrounding style.

## Related issues

<!-- e.g. "Closes #12" -->

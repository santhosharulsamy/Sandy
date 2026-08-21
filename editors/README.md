# Editor integration

- **[`vscode/`](vscode)** — a VS Code extension providing syntax highlighting
  and editor configuration for `.sy` files. Its TextMate grammar
  (`vscode/syntaxes/sandy.tmLanguage.json`, scope `source.sandy`) also works
  in any editor that consumes TextMate grammars.

- **Language server** — richer features (diagnostics, formatting, completion,
  outline) come from the built-in server: `sandy lsp` (LSP over stdio). Point
  any LSP client at `command: "sandy", args: ["lsp"]`.

The grammar's keyword and builtin lists are kept in sync with the language by
`tests/test_grammar.py`.

# Documentation Style Guide

This repository follows concise operator-focused documentation. Write for a
developer or administrator who needs to understand what the automation changes,
where configuration is written, and how to validate the result.

## Language

- Use British English with Oxford spelling.
- Prefer direct active sentences.
- Expand uncommon acronyms on first use.
- Use `code` formatting for commands, file paths, variables, package names and
  module names.

## Structure

- Put the operational summary before implementation detail.
- Keep headings short and descriptive.
- Use bullet lists for procedures and reference material.
- Wrap Markdown paragraphs and bullets at 80 columns.
- Wrap shell and code examples at 120 columns.

## Secrets

- Do not include plaintext secrets in documentation.
- Refer to Ansible Vault variable names rather than secret values.
- Mention local source files for secrets only when the workflow depends on
  them, for example `~/__firecrawl_token`.

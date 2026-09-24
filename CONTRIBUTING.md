# Contributing

In descriptive text, replace long dashes with a short hyphen (`-`). This style
rule applies only to prose descriptions. Do not alter code, command syntax,
identifiers, data, or quoted protocol values to enforce it.

Run `python -m pytest` before submitting a change. Tests must mock EVM sends
and systemd operations; never use production validator keys in tests.

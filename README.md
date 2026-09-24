# Decimal EVM Guardian

An independent, open-source signature guard for Decimal EVM validators. It
checks finalized commit signatures against two independent CometBFT RPCs. If
the configured number of signatures is missed, it submits a freshly signed
EVM `pauseSelf()` transaction. It never activates a validator.

This repository contains only the guard. It does not install a timer, stop the
Decimal service, change `config.toml`, delete blockchain data, or perform
state-sync maintenance.

## Safety

- Compare both RPCs by network, height, commit hash and validator signature.
- Default thresholds: 8 misses in 24 blocks or 6 consecutive misses.
- No transaction on missing, divergent or incomplete RPC data.
- Check EVM chain ID and on-chain paused state before signing.
- Use the pending nonce and serialize sends with a local lock.
- Persist the transaction hash before broadcasting. An unresolved hash blocks
  another transaction until its result is known.
- Check receipt and on-chain state after confirmation.
- Disabled by default. Installation does not start the service.

## Install

Read the [full installation and configuration guide](docs/INSTALL.ru.md).
The release installer downloads a versioned archive and verifies SHA-256:

```bash
curl -fsSLo /tmp/install-decimal-guardian.sh https://github.com/maxwell2010/decimal-evm-guard/releases/latest/download/install-release.sh
sudo bash /tmp/install-decimal-guardian.sh
```

The example config uses placeholder RPCs and no secret. The secret belongs in
a separate root-owned `0600` file outside Git:

```json
{"private_key":"0xREPLACE_WITH_YOUR_PRIVATE_KEY"}
```

Alternatively, use `{"mnemonic":"REPLACE_WITH_YOUR_SECRET_PHRASE"}`.
Mnemonic derivation defaults internally to `m/44'/60'/0'/0/0`; it is not a
configuration field. A private key is safer when a dedicated validator wallet
is available. Never commit or print either secret.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

The test suite mocks transactions and does not submit them to any network.
The old Cosmos-era Decimal Guard was consulted as a design reference, but its
pre-signed transaction mechanism and source code are not used.

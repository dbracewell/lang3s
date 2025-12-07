#!/usr/bin/env bash

cd frontend/lang3s
pnpm run drizzle:json
cd ../../
python scripts/drizzle_codgen.py
rm drizzle-schema.json
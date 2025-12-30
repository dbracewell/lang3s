#!/usr/bin/t3env bash
poetry install
poetry run python setup.py build_ext --inplace
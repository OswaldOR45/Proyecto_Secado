#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Punto de entrada retrocompatible. Equivale a `python -m secado`.
Mantiene el nombre original del archivo para que nadie tenga que cambiar
shortcuts o scripts."""
from secado.__main__ import main
import sys
sys.exit(main())

"""
Globaler Rate Limiter (slowapi) für Brute-Force-Schutz.

Importiert in main.py (Setup) und in auth.py (Decorator).
Gemeinsames Singleton verhindert zirkuläre Imports.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

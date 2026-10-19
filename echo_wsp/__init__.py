"""ECHO-WSP — Wired Symbolic Protocol, the language ECHO agents speak.

Current version: LINK-3. Two or more ECHO agents tell each other what they
lived in 16-byte WSP postcards, by wire or by sound, signed, weighed by a
trust ledger and ranked by risk before value. What one agent hears is
testimony and never becomes a fact in its memory.

    echo_wsp.link1  postcards, modem, dialogue          (LINK-1)
    echo_wsp.link2  consequence, signed envelope, trust (LINK-2)
    echo_wsp.link3  risk hierarchy, voices not keys     (LINK-3, current)
    echo_wsp.nexus0 the ECHO agent core the links run on (vendored)
    echo_wsp.v05    the earlier symbolic-emotional protocol (v0.5)

    python3 -m echo_wsp --help
"""

__version__ = "3.0.0"

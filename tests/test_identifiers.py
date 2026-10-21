import pytest

from photolab.identifiers import FileIdentifier, identify_file


def test_identifier_is_a_known_sha256_of_original_bytes():
    identifier = identify_file(b"abc")
    assert identifier == FileIdentifier(
        sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        size_bytes=3,
    )


def test_identifier_is_stable_and_detects_changed_content():
    original = identify_file(b"IESNA:LM-63-2002\nTILT=NONE\n")
    assert original == identify_file(b"IESNA:LM-63-2002\nTILT=NONE\n")
    assert original.sha256 != identify_file(b"IESNA:LM-63-2002\nTILT=NONE\r\n").sha256


def test_identifier_rejects_non_bytes_content():
    with pytest.raises(TypeError, match="must be bytes"):
        identify_file("not file bytes")  # type: ignore[arg-type]

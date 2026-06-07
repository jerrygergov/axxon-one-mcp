# Problems: phase-37-archive-volume

None. Fresh verifier returned overall PASS on all six acceptance criteria (AC1-AC6).
verdict.json records the PASS. No fixes required.

Honest scope note (not a problem): only ArchiveService.Resize is serviceable on this
stand. ChangeBookmarks is deprecated server-side (UNIMPLEMENTED); CreateReaderEndpoint,
Seek and ClearInterval throw CORBA INTERNAL because the reader / recorded-source subsystem
is not serviceable for the virtual sources here. They are left tested-warn-fixture-needed,
not faked.

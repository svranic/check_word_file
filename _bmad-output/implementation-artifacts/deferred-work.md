# Odgođeni rad

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-postavljanje-projekta-i-objava-prazne-studentske-stranice.md`
  summary: Potvrditi da Streamlit Community Cloud iz `uv.lock` instalira i sam projekt (`provjera`), tako da `apps/student.py` može uvesti jezgru.
  evidence: maybe-false, a ako je točno, ozbiljnost je high (neprovjereno). Streamlit na `sys.path` stavlja `apps/`, a ne korijen repozitorija. Lokalno `uv sync` instalira paket kao editable i test to sada provjerava izvan korijena. Pitanje razrješava prvi deploy: stranica se mora otvoriti bez `ModuleNotFoundError: provjera`. Ako padne, rješenje je instalacija projekta na Cloudu ili `sys.path` bootstrap u `apps/`.

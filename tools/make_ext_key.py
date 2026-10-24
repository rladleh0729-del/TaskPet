# 확장 프로그램 ID를 고정하기 위한 키를 만든다 (한 번만 실행).
# 압축 해제된 확장은 폴더 위치에 따라 ID가 바뀌는데, manifest.json에 공개 키("key")를 넣으면
# 어디서 불러와도 같은 ID가 되어 Native Messaging 허용 목록(allowed_origins)에 미리 적어 둘 수 있다.
#   python tools\make_ext_key.py   → extension_key.pem(비공개, 저장소에 올리지 않음), 공개 키·ID 출력
import base64
import hashlib
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PEM = os.path.join(ROOT, "extension_key.pem")

if os.path.exists(PEM):
    key = serialization.load_pem_private_key(open(PEM, "rb").read(), password=None)
else:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with open(PEM, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))

der = key.public_key().public_bytes(serialization.Encoding.DER,
                                    serialization.PublicFormat.SubjectPublicKeyInfo)
digest = hashlib.sha256(der).hexdigest()[:32]
ext_id = "".join(chr(ord("a") + int(c, 16)) for c in digest)
print("KEY", base64.b64encode(der).decode())
print("ID", ext_id)

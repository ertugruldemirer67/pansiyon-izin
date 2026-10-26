from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .models import Kullanici
from .security import jetondan_kullanici_id


def get_db(request: Request):
    db = request.app.state.oturum_fabrikasi()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def mevcut_kullanici(request: Request, db: Session = Depends(get_db)) -> Kullanici:
    jeton = request.cookies.get("oturum")
    yetki = request.headers.get("authorization", "")
    if not jeton and yetki.lower().startswith("bearer "):
        jeton = yetki[7:].strip()
    kid = jetondan_kullanici_id(jeton) if jeton else None
    kullanici = db.get(Kullanici, kid) if kid else None
    if kullanici is None or not kullanici.aktif:
        raise HTTPException(401, "Giriş gerekli")
    return kullanici


def rol_gerekli(*roller: str):
    def kontrol(kullanici: Kullanici = Depends(mevcut_kullanici)) -> Kullanici:
        if kullanici.rol not in roller:
            raise HTTPException(403, "Bu işlem için yetkiniz yok")
        return kullanici

    return kontrol

from app.database import Base, SessionLocal, engine
from app.seed.data import seed_demo


def reset_demo() -> None:
    from app import models  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_demo(session)


if __name__ == "__main__":
    reset_demo()
    print("Deterministic demo data reset: C001-C004")


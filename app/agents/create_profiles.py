from app.db.database import SessionLocal
from app.agents.profiles import create_pilot_profiles

def main():
  db = SessionLocal()

  try:
    create_pilot_profiles(db)
  finally:
    db.close()


if __name__ == "__main__":
  main()
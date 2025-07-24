from sqlalchemy import create_engine, Column, Integer, String, Date, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class MLBGame(Base):
    __tablename__ = 'mlb_games'
    id = Column(Integer, primary_key=True)
    game_date = Column(Date, nullable=False)
    game_time = Column(Time, nullable=True)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    venue = Column(String, nullable=True)
    game_id = Column(String, nullable=True)  # External/game API id


def get_engine(db_url='sqlite:///mlb_schedule.db'):
    return create_engine(db_url)


def create_tables(engine):
    Base.metadata.create_all(engine)


def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()


def add_game(session, game_info):
    game = MLBGame(**game_info)
    session.add(game)
    session.commit()
    return game


def get_games_by_date(session, date):
    return session.query(MLBGame).filter_by(game_date=date).all()

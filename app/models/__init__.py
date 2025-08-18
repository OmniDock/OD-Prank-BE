from .base import Base
from .scenario import Scenario
from .voice_line import VoiceLine
import sqlalchemy_continuum

# Initialize continuum (Similar to Django's django-simple-history)
sqlalchemy_continuum.make_versioned(user_cls=None)
sqlalchemy_continuum.configure(Base)

__all__ = ["Base", "Scenario", "VoiceLine"]
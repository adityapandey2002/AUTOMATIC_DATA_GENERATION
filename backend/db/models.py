"""SQLAlchemy models for the ambient scribe database."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Boolean,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Encounter(Base):
    __tablename__ = "encounters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    clinic_id = Column(String(100), default="")
    language_detected = Column(String(50), default="")
    status = Column(String(20), default="active")  # active | finalized | confirmed
    consent_given = Column(Boolean, default=False)

    patient = relationship("Patient", back_populates="encounter", uselist=False)
    utterances = relationship("Utterance", back_populates="encounter")
    vitals_snapshots = relationship("VitalsSnapshot", back_populates="encounter")
    alerts = relationship("Alert", back_populates="encounter")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=False)
    name = Column(String(200), nullable=True)
    age = Column(Integer, nullable=True)
    language = Column(String(50), nullable=True)
    spouse_parent_of = Column(String(200), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    district = Column(String(100), nullable=True)
    block = Column(String(100), nullable=True)
    health_centre = Column(String(200), nullable=True)
    answers = Column(JSON, nullable=True, default=dict)
    saved_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    encounter = relationship("Encounter", back_populates="patient")


class Utterance(Base):
    __tablename__ = "utterances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=False)
    chunk_id = Column(Integer, nullable=False)
    speaker = Column(String(20), default="unknown")  # patient | gnm | unknown
    transcript = Column(Text, default="")
    language = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    encounter = relationship("Encounter", back_populates="utterances")


class VitalsSnapshot(Base):
    __tablename__ = "vitals_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    data = Column(JSON, nullable=False, default=dict)
    confirmed = Column(Boolean, default=False)

    encounter = relationship("Encounter", back_populates="vitals_snapshots")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    field = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="warning")  # warning | critical
    acknowledged = Column(Boolean, default=False)

    encounter = relationship("Encounter", back_populates="alerts")


class AudioDeletionLog(Base):
    __tablename__ = "audio_deletion_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=False)
    chunk_ids = Column(JSON, default=list)
    deleted_at = Column(DateTime, default=datetime.utcnow)
    deletion_reason = Column(String(200), default="transcribe_complete")

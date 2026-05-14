from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
import datetime
from backend.database import Base

# Tabla intermedia Muchos a Muchos (Usuarios <-> Restricciones)
usuario_restriccion = Table(
    'usuario_restriccion',
    Base.metadata,
    Column('usuario_id', Integer, ForeignKey('usuarios.id', ondelete="CASCADE"), primary_key=True),
    Column('restriccion_id', Integer, ForeignKey('restricciones.id', ondelete="CASCADE"), primary_key=True)
)

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    nombre = Column(String)
    fecha_registro = Column(DateTime, default=datetime.datetime.utcnow)
    
    restricciones = relationship("Restriccion", secondary=usuario_restriccion, back_populates="usuarios")
    historial = relationship("HistorialProducto", back_populates="usuario", cascade="all, delete-orphan")

class Restriccion(Base):
    __tablename__ = "restricciones"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True)
    tipo = Column(String)
    
    usuarios = relationship("Usuario", secondary=usuario_restriccion, back_populates="restricciones")

class HistorialProducto(Base):
    __tablename__ = "historial_producto"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"))
    fecha_hora_escaneo = Column(DateTime, default=datetime.datetime.utcnow)
    
    desc_breve_producto = Column(String)
    es_apto = Column(Boolean)
    ingredientes_peligrosos = Column(ARRAY(String)) # Exclusivo de Postgres
    razon_alerta = Column(String)
    imagen_base64 = Column(Text)
    respuesta_json_llm = Column(JSONB)              # Exclusivo de Postgres
    
    usuario = relationship("Usuario", back_populates="historial")
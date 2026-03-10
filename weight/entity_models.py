"""Database entity models for weight microservice"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class Container:
    """Container registered with tara weight"""
    container_id: str
    weight: Optional[int] = None
    unit: Optional[str] = None
    
    @classmethod
    def from_db_row(cls, row: dict) -> 'Container':
        """Convert database row to Container object"""
        return cls(
            container_id=row['container_id'],
            weight=row.get('weight'),
            unit=row.get('unit')
        )
    
    def to_db_dict(self) -> dict:
        """Convert Container object to database insert/update dict"""
        return {
            'container_id': self.container_id,
            'weight': self.weight,
            'unit': self.unit
        }


@dataclass
class Transaction:
    """Weight measurement session (transaction)"""
    id: Optional[int] = None
    datetime: Optional[datetime] = None
    direction: Optional[str] = None  # "in", "out", "none"
    truck: Optional[str] = None
    containers: Optional[List[str]] = None  # List of container IDs
    bruto: Optional[int] = None
    truck_tara: Optional[int] = None
    neto: Optional[int] = None
    produce: Optional[str] = None
    session_id: Optional[int] = None
    
    @classmethod
    def from_db_row(cls, row: dict) -> 'Transaction':
        """Convert database row to Transaction object"""
        containers_str = row.get('containers') or ''
        containers = [c.strip() for c in containers_str.split(',') if c.strip()] if containers_str else []
        
        return cls(
            id=row.get('id'),
            datetime=row.get('datetime'),
            direction=row.get('direction'),
            truck=row.get('truck'),
            containers=containers,
            bruto=row.get('bruto'),
            truck_tara=row.get('truckTara'),
            neto=row.get('neto'),
            produce=row.get('produce'),
            session_id=row.get('sessionId')
        )
    
    def to_db_dict(self) -> dict:
        """Convert Transaction object to database insert/update dict"""
        containers_csv = ','.join(self.containers) if self.containers else None
        
        return {
            'datetime': self.datetime,
            'direction': self.direction,
            'truck': self.truck,
            'containers': containers_csv,
            'bruto': self.bruto,
            'truckTara': self.truck_tara,
            'neto': self.neto,
            'produce': self.produce,
            'sessionId': self.session_id
        }
    
    def to_json(self) -> dict:
        """Convert to JSON-friendly dict for API responses"""
        return {
            'id': self.id,
            'datetime': self.datetime.isoformat() if self.datetime else None,
            'direction': self.direction,
            'truck': self.truck,
            'containers': self.containers or [],
            'bruto': self.bruto,
            'truckTara': self.truck_tara or 0,
            'neto': self.neto or 0,
            'produce': self.produce,
            'sessionId': self.session_id
        }

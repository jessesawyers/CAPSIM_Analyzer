from enum import Enum


class Segment(str, Enum):
    TRADITIONAL = "Traditional"
    LOW_END = "Low End"
    HIGH_END = "High End"
    PERFORMANCE = "Performance"
    SIZE = "Size"


class Company(str, Enum):
    ANDREWS = "Andrews"
    BALDWIN = "Baldwin"
    CHESTER = "Chester"
    DIGBY = "Digby"
    ERIE = "Erie"
    FERRIS = "Ferris"

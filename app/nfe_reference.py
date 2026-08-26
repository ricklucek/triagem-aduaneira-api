"""Referências controladas do leiaute da NF-e."""


NFE_TRANSPORT_MODES = {
    "1": "Marítima",
    "2": "Fluvial",
    "3": "Lacustre",
    "4": "Aérea",
    "5": "Postal",
    "6": "Ferroviária",
    "7": "Rodoviária",
    "8": "Conduto",
    "9": "Meios próprios",
    "10": "Entrada/saída ficta",
    "11": "Courier",
    "12": "Em mãos",
    "13": "Por reboque",
}

NFE_TRANSPORT_MODE_CODES = frozenset(NFE_TRANSPORT_MODES)

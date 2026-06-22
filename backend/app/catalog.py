"""Series catalog and the credit-card <-> CPI category mapping.

Populated from the user's real EVDS codes + the "Kart ve TÜİK Bileşenleri"
mapping spreadsheet.

EVDS code patterns
------------------
  Credit card amount : TP.KKHARTUT.KT<n>     (weekly)
  Credit card count  : TP.KKISLADE.KA<n>      (weekly)
  TÜİK CPI (2025=100): TP_TUKFIY2025_<COICOP> (monthly); general index = GENEL
  İTO                : not implemented yet

The TÜİK column in the spreadsheet gives one or more COICOP sub-indices with
basket weights, e.g. "071*5,1178 + 0723*0,9917". Those become a weighted
composite index (weights normalised at compute time). "-" => no TÜİK mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Freq(int, Enum):
    WEEKLY = 3
    MONTHLY = 5


class SeriesKind(str, Enum):
    CC_AMOUNT = "cc_amount"
    CC_COUNT = "cc_count"
    CPI_TUIK = "cpi_tuik"
    CPI_ITO = "cpi_ito"


@dataclass(frozen=True)
class Series:
    code: str
    name: str
    kind: SeriesKind
    freq: Freq


@dataclass(frozen=True)
class CCCategory:
    key: str
    label: str
    amount_code: str
    count_code: str


@dataclass(frozen=True)
class Mapping:
    cc_key: str
    tuik_codes: list[str] = field(default_factory=list)
    ito_codes: list[str] = field(default_factory=list)
    weights_tuik: list[float] = field(default_factory=list)
    weights_ito: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Source data: CC category index -> (label, [(COICOP code, weight), ...])
# Index matches the EVDS suffix: amount=TP.KKHARTUT.KT<n>, count=TP.KKISLADE.KA<n>
# ---------------------------------------------------------------------------
_CC: dict[int, tuple[str, list[tuple[str, float]]]] = {
    1:  ("TOPLAM", [("GENEL", 1.0)]),
    2:  ("Araba Kiralama", [("07244", 1.0)]),  # 0724401 (7 hane) EVDS'de yok; 07244 yayınlanan en alt seviye
    3:  ("Araç Kiralama-Satış/Servis/Yedek Parça", [("071", 5.1178), ("0723", 0.9917)]),
    4:  ("Benzin ve Yakıt İstasyonları", [("0722", 1.0)]),
    5:  ("Çeşitli Gıda", [("011", 1.0)]),
    6:  ("Doğrudan Pazarlama", [("03", 7.9), ("05", 7.92)]),
    7:  ("Eğitim / Kırtasiye / Ofis Malzemeleri", [("10", 2.02), ("097", 0.51)]),
    8:  ("Elektrik-Elektronik Eşya, Bilgisayar", [("081", 1.47), ("053", 1.94)]),
    9:  ("Giyim ve Aksesuar", [("03", 1.0)]),
    10: ("Havayolları", [("0733", 1.0)]),
    11: ("Hizmet Sektörleri", [("0314", 0.0909), ("1313", 0.5853), ("092", 0.4268)]),
    12: ("Konaklama", [("112", 1.0)]),
    13: ("Kulüp / Dernek / Sosyal Hizmetler", []),
    14: ("Kumarhane / İçkili Yerler", []),
    15: ("Kuyumcular", []),
    16: ("Market ve Alışveriş Merkezleri", [("01", 24.44), ("02", 2.7549), ("1312", 1.22)]),
    17: ("Mobilya ve Dekorasyon", [("05", 1.0)]),
    18: ("Müteahhit İşleri", []),
    19: ("Sağlık/Sağlık Ürünleri/Kozmetik", [("06", 1.0)]),
    20: ("Seyahat Acenteleri/Taşımacılık", [("098", 0.59), ("073", 6.14)]),
    21: ("Sigorta", [("121", 1.0)]),
    22: ("Telekomünikasyon", [("083", 1.0)]),
    23: ("Yapı Malzemeleri, Hırdavat, Nalburiye", [("0431", 1.0)]),
    24: ("Yemek", [("11", 1.0)]),
    25: ("Kamu/Vergi Ödemeleri", []),
    26: ("Bireysel Emeklilik", []),
    49: ("Diğer", []),
    50: ("Bilgi için: İnternet Üzerinden Yapılan Alışverişler", []),
    51: ("Bilgi için: Mektupla/Telefonla Yapılan Alışverişler", []),
    52: ("Bilgi için: Gümrük Vergisi Ödemeleri", []),
}


# Official TÜFE (2025=100) sub-index names, sourced from EVDS datagroup
# bie_tukfiy2025 (leading "NNN. " prefix stripped). Keep in sync if the
# mapping gains new COICOP codes.
COICOP_LABELS: dict[str, str] = {
    "GENEL": "Genel Endeks",
    "01": "Gıda Ve Alkolsüz İçecekler",
    "011": "Gıda",
    "02": "Alkollü İçecekler, Tütün Ve Tütün Ürünleri",
    "03": "Giyim Ve Ayakkabı",
    "0314": "Giyim Eşyalarının Temizlenmesi, Onarımı, Tadilatı, Dikimi Ve Kiralanması",
    "0431": "Konutun Bakım Ve Onarımı İçin Malzemeler Ve Güvenlik Ekipmanları",
    "05": "Mobilya, Mefruşat, Ev Ekipmanları Ve Rutin Ev Bakımı",
    "053": "Ev Aletleri",
    "06": "Sağlık",
    "071": "Araç Satın Alımı",
    "0722": "Kişisel Ulaşım Araçları İçin Yakıtlar Ve Yağlar",
    "0723": "Kişisel Ulaşım Araçlarının Bakım Ve Onarımı",
    "07244": "Kişisel Ulaşım Araçlarının Sürücüsüz Olarak Kiralanması",
    "073": "Yolcu Taşıma Hizmetleri",
    "0733": "Hava Yolu İle Yolcu Taşımacılığı",
    "081": "Bilgi Ve İletişim Ekipmanları",
    "083": "Bilgi Ve İletişim Hizmetleri",
    "092": "Diğer Eğlence Malları",
    "097": "Gazete, Kitap Ve Kırtasiye Malzemeleri",
    "098": "Paket Turlar Ve Tatiller",
    "10": "Eğitim Hizmetleri",
    "11": "Lokantalar Ve Konaklama Hizmetleri",
    "112": "Konaklama Hizmetleri",
    "121": "Sigorta",
    "1312": "Kişisel Bakıma Yönelik Diğer Aletler, Malzemeler Ve Ürünler",
    "1313": "Kuaför Salonları Ve Kişisel Bakım Merkezleri",
    # 724401: EVDS bie_tukfiy2025'te bulunmuyor (veri dönmüyor).
}


def coicop_label(coicop: str) -> str:
    """Display label including the COICOP code, e.g. '011 · Gıda'."""
    desc = COICOP_LABELS.get(coicop)
    return f"{coicop} · {desc}" if desc else f"{coicop} · (EVDS'de tanımsız)"


# İTO Geçinme Endeksi (1995=100) main spending groups -> code TP.FG.<grp>.95
ITO_LABELS: dict[str, str] = {
    "B01": "Genel Endeks",
    "B02": "Gıda Harcamaları",
    "B03": "Konut Harcamaları",
    "B04": "Ev Eşyası Harcamaları",
    "B05": "Giyim Harcamaları",
    "B06": "Sağlık, Kişisel Bakım Harcamaları",
    "B07": "Ulaştırma ve Haberleşme Harcamaları",
    "B08": "Kültür, Eğitim ve Eğlence Harcamaları",
    "B09": "Diğer Harcamalar",
}


def component_meta(code: str) -> tuple[str, str]:
    """Map a CPI series code -> (component key, display label).

    Works for both TÜİK (TP.TUKFIY2025.<coicop>) and İTO (TP.FG.<grp>.95).
    """
    if code.startswith("TP.TUKFIY2025."):
        coicop = code.split(".")[-1]
        return f"c_{coicop}", coicop_label(coicop)
    if code.startswith("TP.FG.") and code.endswith(".95"):
        grp = code.split(".")[2]
        return f"ito_{grp}", f"{grp} · {ITO_LABELS.get(grp, grp)}"
    return code.replace(".", "_"), code


def _amount_code(n: int) -> str:
    return f"TP.KKHARTUT.KT{n}"


def _count_code(n: int) -> str:
    return f"TP.KKISLADE.KA{n}"


def _tuik_code(coicop: str) -> str:
    # EVDS expects dotted codes in the series= param (the underscore form the
    # mapping used is just notation): TP.TUKFIY2025.GENEL, TP.TUKFIY2025.011, ...
    return f"TP.TUKFIY2025.{coicop}"


def _ito_code(grp: str) -> str:
    return f"TP.FG.{grp}.95"


# CC category index -> İTO Geçinme Endeksi (1995=100) main group, or None.
# Each maps to a single group (weight 1.0). "-"/blank in the sheet => None.
_ITO_MAP: dict[int, str | None] = {
    1: "B01",   # TOPLAM -> Genel Endeks
    4: "B07",   # Benzin ve Yakıt İstasyonları
    5: "B02",   # Çeşitli Gıda
    7: "B08",   # Eğitim / Kırtasiye / Ofis Malzemeleri
    8: "B04",   # Elektrik-Elektronik Eşya, Bilgisayar
    9: "B05",   # Giyim ve Aksesuar
    10: "B07",  # Havayolları
    16: "B02",  # Market ve Alışveriş Merkezleri
    17: "B04",  # Mobilya ve Dekorasyon
    19: "B06",  # Sağlık/Sağlık Ürünleri/Kozmetik
    20: "B07",  # Seyahat Acenteleri/Taşımacılık
    23: "B04",  # Yapı Malzemeleri, Hırdavat, Nalburiye
    24: "B02",  # Yemek
}


# ---------------------------------------------------------------------------
# Build SERIES, CC_CATEGORIES, MAPPING from the source table
# ---------------------------------------------------------------------------
SERIES: list[Series] = []
CC_CATEGORIES: list[CCCategory] = []
MAPPING: list[Mapping] = []

_seen_cpi: set[str] = set()

for n, (label, coicop_weights) in _CC.items():
    key = f"kt{n}"
    SERIES.append(Series(_amount_code(n), f"Kredi Kartı Harcama Tutarı - {label}",
                         SeriesKind.CC_AMOUNT, Freq.WEEKLY))
    SERIES.append(Series(_count_code(n), f"Kredi Kartı İşlem Adedi - {label}",
                         SeriesKind.CC_COUNT, Freq.WEEKLY))
    CC_CATEGORIES.append(CCCategory(key, label, _amount_code(n), _count_code(n)))

    # --- TÜİK deflator components ---
    tuik_codes = [_tuik_code(c) for c, _ in coicop_weights]
    tuik_w = [w for _, w in coicop_weights]
    for code, c in zip(tuik_codes, [c for c, _ in coicop_weights]):
        if code not in _seen_cpi:
            _seen_cpi.add(code)
            name = "TÜFE - Genel" if c == "GENEL" else f"TÜFE - {c}"
            SERIES.append(Series(code, name, SeriesKind.CPI_TUIK, Freq.MONTHLY))

    # --- İTO deflator component (single group, if mapped) ---
    grp = _ITO_MAP.get(n)
    ito_codes: list[str] = []
    ito_w: list[float] = []
    if grp:
        ic = _ito_code(grp)
        ito_codes = [ic]
        ito_w = [1.0]
        if ic not in _seen_cpi:
            _seen_cpi.add(ic)
            SERIES.append(Series(ic, f"İTO 1995=100 - {ITO_LABELS.get(grp, grp)}",
                                 SeriesKind.CPI_ITO, Freq.MONTHLY))

    MAPPING.append(Mapping(cc_key=key, tuik_codes=tuik_codes, weights_tuik=tuik_w,
                           ito_codes=ito_codes, weights_ito=ito_w))


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
SERIES_BY_CODE: dict[str, Series] = {s.code: s for s in SERIES}
CC_BY_KEY: dict[str, CCCategory] = {c.key: c for c in CC_CATEGORIES}
MAPPING_BY_KEY: dict[str, Mapping] = {m.cc_key: m for m in MAPPING}


def all_series_codes() -> list[str]:
    return [s.code for s in SERIES]


def is_configured() -> bool:
    return not any("PLACEHOLDER" in c for c in all_series_codes())

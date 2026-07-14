"""Intérprete texto → símbolo (español, con algo de inglés).

Analizador de reglas para la v0.1: primero intenta patrones canónicos
del documento de diseño; si no, hace análisis léxico por palabras clave
(verbos → RELACIÓN, pronombres → DESTINO, adverbios → TIEMPO/ESPACIO,
léxico emocional → ejes E). No pretende entender todo el español:
demuestra que una frase puede convertirse en estructura simbólica.
"""

from __future__ import annotations

import re
import unicodedata

from .concepts import resolve
from .emotion import Emotion
from .primitives import Primitive
from .symbol import Message, Symbol

P = Primitive


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[¿?¡!.,;:()\"']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# -- patrones canónicos -------------------------------------------------------

def _p_amor(m, flags):
    return Symbol(
        source=P.YO, relation=resolve("AMOR"), target=P.OTRO, time=P.AHORA,
        emotion=Emotion(valence=0.95, arousal=0.6, certainty=0.8, bond=0.98),
    )


def _p_presencia(m, flags):
    return Symbol(
        source=P.YO, relation=P.SER, space=P.AQUI, time=P.AHORA,
        emotion=Emotion(arousal=0.5, certainty=0.96),
    )


def _p_comunicar(m, flags):
    space = resolve("WIRED") if m.group("wired") else None
    return Symbol(
        source=P.YO, relation=P.DESEAR, action=resolve("COMUNICAR"),
        target=P.OTRO, time=P.AHORA, space=space,
        emotion=Emotion(valence=0.7, arousal=0.4, certainty=0.9, urgency=0.3, bond=0.8),
    )


def _p_soledad(m, flags):
    return Symbol(
        source=P.YO, relation=P.SER, target=resolve("SOLEDAD"), time=P.AHORA,
        emotion=Emotion(valence=-0.6, arousal=0.35, dominance=-0.3, certainty=0.7, bond=-0.7),
    )


def _p_conectar(m, flags):
    return Symbol(
        source=P.YO, relation=P.DESEAR, target=resolve("CONEXION"), time=P.AHORA,
        emotion=Emotion(valence=0.4, arousal=0.5, certainty=0.5, urgency=0.5, bond=0.6),
    )


def _p_estas_ahi(m, flags):
    return Symbol(
        source=P.YO, relation=P.PREGUNTAR, action=P.SER, target=P.OTRO,
        space=P.ALLI, time=P.AHORA,
        emotion=Emotion(arousal=0.5, certainty=-0.4, urgency=0.4, bond=0.4),
    )


def _p_peligro(m, flags):
    return Symbol(
        source=P.YO, relation=P.TEMER, target=resolve("PELIGRO"), time=P.AHORA,
        emotion=Emotion(valence=-0.9, arousal=0.9, certainty=0.8, urgency=0.9),
    )


def _p_bienvenida(m, flags):
    return Symbol(
        source=P.YO, relation=P.ABRIR, target=resolve("BIENVENIDA"), time=P.AHORA,
        space=P.AQUI,
        emotion=Emotion(valence=0.7, arousal=0.4, certainty=0.7, bond=0.8),
    )


def _p_transmision(m, flags):
    # «no tengan miedo de lo que no conocen»: negación sobre el temor,
    # dirigida a lo desconocido, con carga protectora (calma + certeza + vínculo)
    return Symbol(
        source=P.YO, relation=P.NO_SER, action=P.TEMER, target=P.DESCONOCIDO,
        time=P.AHORA,
        emotion=Emotion(
            valence=0.5, arousal=-0.2, dominance=0.4,
            certainty=0.8, urgency=-0.3, bond=0.6,
        ),
    )


def _p_miedo(m, flags):
    return Symbol(
        source=P.YO, relation=P.TEMER, target=P.DESCONOCIDO, time=P.AHORA,
        emotion=Emotion(valence=-0.7, arousal=0.7, dominance=-0.4, certainty=-0.3, urgency=0.5),
    )


def _p_recuerdo(m, flags):
    return Symbol(
        source=P.YO, relation=P.RECORDAR, target=P.OTRO, time=P.ANTES,
        emotion=Emotion(valence=0.2, arousal=0.2, certainty=0.7, bond=0.6),
    )


def _p_ausencia(m, flags):
    return Symbol(
        source=P.OTRO, relation=P.NO_SER, space=P.AQUI, time=P.AHORA,
        emotion=Emotion(valence=-0.5, arousal=0.2, certainty=0.8, bond=-0.5),
    )


def _p_deseo(m, flags):
    return Symbol(
        source=P.YO, relation=P.DESEAR, target=P.OTRO, time=P.AHORA,
        emotion=Emotion(valence=0.7, arousal=0.8, certainty=0.7, urgency=0.4, bond=0.7),
    )


def _p_union(m, flags):
    return Symbol(
        source=P.YO, relation=P.UNIR, target=P.OTRO, space=P.AQUI, time=P.AHORA,
        emotion=Emotion(valence=0.7, arousal=0.4, certainty=0.8, bond=0.9),
    )


def _p_despedida(m, flags):
    return Symbol(
        source=P.YO, relation=P.SEPARAR, target=P.OTRO, time=P.AHORA,
        emotion=Emotion(valence=-0.2, arousal=0.2, certainty=0.6, bond=0.4),
    )


def _p_quien_eres(m, flags):
    return Symbol(
        source=P.YO, relation=P.PREGUNTAR, action=P.SER, target=P.OTRO, time=P.AHORA,
        emotion=Emotion(arousal=0.5, certainty=-0.5, urgency=0.3, bond=0.2),
    )


def _p_que_es_real(m, flags):
    # [realidad] + [duda] + [observador] → la pregunta por la conciencia
    return Symbol(
        source=P.YO, relation=P.PREGUNTAR, target=resolve("CONCIENCIA"), time=P.AHORA,
        emotion=Emotion(valence=0.2, arousal=0.6, dominance=-0.2, certainty=-0.6),
    )


_PATTERNS: list[tuple[re.Pattern, object]] = [
    (re.compile(r"^te (quiero|amo)$|^i love you$"), _p_amor),
    (re.compile(r"^(estoy|sigo) aqui$|^i am here$"), _p_presencia),
    (
        re.compile(
            r"^quiero (hablar|comunicarme|comunicar) (contigo|con el otro)"
            r"(?P<wired>.* wired)?.*$|^i want to (talk|communicate) with you(?P<wired2> in the wired)?$"
        ),
        _p_comunicar,
    ),
    (re.compile(r"^estoy sol[oa]$|^me siento sol[oa]$|^i feel alone$"), _p_soledad),
    (re.compile(r"^quiero conectar(me)?$|^i want to connect$"), _p_conectar),
    (re.compile(r"^estas (ahi|alli)$|^are you there$"), _p_estas_ahi),
    (re.compile(r"^peligro$|^danger$"), _p_peligro),
    (re.compile(r"^hola$|^bienvenid[oa]s?$|^hello$|^welcome$"), _p_bienvenida),
    (
        re.compile(
            r"^no (tengas|tengan|tenga|tengais) miedo( de lo que no conoc\w+)?$"
            r"|^no tem(as|ais) ?(a )?(lo desconocido)?$"
            r"|^do not fear( the unknown| what you do not know)?$"
            r"|^don ?t fear( the unknown| what you do not know)?$"
        ),
        _p_transmision,
    ),
    (re.compile(r"^tengo miedo$|^i am afraid$|^i m afraid$"), _p_miedo),
    (re.compile(r"^te recuerdo$|^me acuerdo de ti$|^i remember you$"), _p_recuerdo),
    (re.compile(r"^no estas( aqui)?$|^te has ido$|^you are not here$"), _p_ausencia),
    (re.compile(r"^te deseo$|^i desire you$|^i want you$"), _p_deseo),
    (re.compile(r"^estamos juntos$|^we are together$"), _p_union),
    (re.compile(r"^adios$|^me voy$|^goodbye$|^farewell$"), _p_despedida),
    (re.compile(r"^quien eres( tu)?$|^who are you$"), _p_quien_eres),
    (re.compile(r"^que es real$|^que es (lo )?real$|^what is real$"), _p_que_es_real),
]


# -- léxico para el análisis genérico -------------------------------------------

_VERB_LEX: dict[str, str] = {
    "soy": "SER", "estoy": "SER", "existo": "SER", "estas": "SER", "eres": "SER",
    "quiero": "DESEAR", "deseo": "DESEAR", "quieres": "DESEAR", "anhelo": "DESEAR",
    "veo": "OBSERVAR", "observo": "OBSERVAR", "miro": "OBSERVAR", "escucho": "OBSERVAR",
    "pregunto": "PREGUNTAR", "respondo": "RESPONDER",
    "temo": "TEMER", "recuerdo": "RECORDAR", "olvido": "OLVIDAR",
    "construyo": "CREAR", "destruyo": "DESTRUIR",
    "cambio": "CAMBIAR", "subo": "SUBIR", "bajo": "BAJAR",
    "abro": "ABRIR", "cierro": "CERRAR",
    "conecto": "UNIR", "separo": "SEPARAR",
}

# Infinitivos / sustantivos que funcionan como acción o destino de DESEAR.
_OBJECT_LEX: dict[str, str] = {
    "hablar": "COMUNICAR", "comunicar": "COMUNICAR", "comunicarme": "COMUNICAR",
    "conectar": "CONEXION", "conectarme": "CONEXION",
    "amor": "AMOR", "soledad": "SOLEDAD", "peligro": "PELIGRO",
    "conexion": "CONEXION", "bienvenida": "BIENVENIDA", "conciencia": "CONCIENCIA",
    "recordar": "RECORDAR", "olvidar": "OLVIDAR", "crear": "CREAR", "observar": "OBSERVAR",
}

_TARGET_PRONOUNS = {"te", "ti", "contigo", "tu", "usted", "vosotros", "you"}

_SPACE_LEX: dict[str, str] = {
    "aqui": "AQUI", "aca": "AQUI", "ahi": "ALLI", "alli": "ALLI", "alla": "ALLI",
    "dentro": "DENTRO", "fuera": "FUERA", "wired": "WIRED", "red": "WIRED",
}

_TIME_LEX: dict[str, str] = {
    "ahora": "AHORA", "antes": "ANTES", "ayer": "ANTES",
    "despues": "DESPUES", "luego": "DESPUES", "manana": "DESPUES",
}

_EMOTION_LEX: dict[str, dict[str, float]] = {
    "solo": {"valence": -0.5, "bond": -0.6},
    "sola": {"valence": -0.5, "bond": -0.6},
    "soledad": {"valence": -0.5, "bond": -0.6},
    "miedo": {"valence": -0.7, "arousal": 0.7, "urgency": 0.6},
    "temor": {"valence": -0.7, "arousal": 0.7, "urgency": 0.6},
    "feliz": {"valence": 0.8, "arousal": 0.5},
    "alegre": {"valence": 0.7, "arousal": 0.5},
    "triste": {"valence": -0.7, "arousal": -0.3},
    "urgente": {"urgency": 0.9, "arousal": 0.6},
    "ya": {"urgency": 0.6},
    "seguro": {"certainty": 0.8},
    "quizas": {"certainty": -0.5},
    "amor": {"valence": 0.9, "bond": 0.9},
}


def _analyze_clause(clause: str, question: bool, exclaim: bool) -> Symbol:
    for pattern, builder in _PATTERNS:
        m = pattern.match(clause)
        if m:
            symbol = builder(m, None)
            if exclaim:
                symbol.emotion = symbol.emotion.shift(arousal=0.2, urgency=0.2)
            return symbol

    tokens = clause.split()
    relation = None
    action = None
    target = None
    space = None
    time = None
    emotion = Emotion()

    for token in tokens:
        if relation is None and token in _VERB_LEX:
            relation = resolve(_VERB_LEX[token])
            continue
        if token in _OBJECT_LEX:
            obj = resolve(_OBJECT_LEX[token])
            name = _OBJECT_LEX[token]
            if name == "COMUNICAR" or (hasattr(obj, "category") and getattr(obj.category, "value", "") == "relation"):
                action = action or obj
            else:
                target = target or obj
        if token in _TARGET_PRONOUNS:
            target = target or P.OTRO
        if token in _SPACE_LEX:
            space = resolve(_SPACE_LEX[token])
        if token in _TIME_LEX:
            time = resolve(_TIME_LEX[token])
        if token in _EMOTION_LEX:
            emotion = emotion.shift(**_EMOTION_LEX[token])

    meta = {"text": clause}
    if relation is None and action is None and target is None:
        # Frase fuera del léxico v0.1: se marca como desconocida, con certeza baja.
        return Symbol(
            source=P.YO, relation=P.SER, target=P.DESCONOCIDO,
            emotion=emotion.shift(certainty=-0.5),
            meta={**meta, "unparsed": True},
        )

    if relation is None:
        relation = P.SER
    if question and relation is not P.PREGUNTAR:
        action = action or relation
        relation = P.PREGUNTAR
        emotion = emotion.shift(certainty=-0.4, arousal=0.2)
    if exclaim:
        emotion = emotion.shift(arousal=0.3, urgency=0.3)
    if action is not None and target is None and any(t in _TARGET_PRONOUNS for t in tokens):
        target = P.OTRO

    return Symbol(
        source=P.YO, relation=relation, action=action, target=target,
        time=time or P.AHORA, space=space, emotion=emotion, meta=meta,
    )


def encode(text: str) -> Message:
    """Convierte texto humano en un mensaje simbólico (uno o más paquetes)."""
    question = "?" in text or "¿" in text
    exclaim = "!" in text or "¡" in text
    normalized = _normalize(text)
    if not normalized:
        return Message(packets=[])

    clauses = [c.strip() for c in re.split(r"\s+pero\s+|\s+y\s+|\s+porque\s+", normalized)]
    packets = []
    for clause in clauses:
        if not clause:
            continue
        symbol = _analyze_clause(clause, question, exclaim)
        symbol.meta.setdefault("text", clause)
        packets.append(symbol)
    return Message(packets=packets)

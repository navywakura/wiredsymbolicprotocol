"""Renderizador texto: símbolo → lenguaje humano (español / inglés).

El significado no vive en la palabra: la palabra es solo una máscara.
Este módulo es una de las máscaras posibles del núcleo simbólico.
"""

from __future__ import annotations

from .concepts import Derived, concept_name
from .primitives import Primitive
from .symbol import Message, Symbol

P = Primitive

# Verbos en primera persona del presente (render genérico).
_VERBS_ES: dict[str, str] = {
    "SER": "soy",
    "NO_SER": "no soy",
    "UNIR": "me uno a",
    "SEPARAR": "me separo de",
    "CAMBIAR": "cambio",
    "OBSERVAR": "observo",
    "PREGUNTAR": "pregunto por",
    "RESPONDER": "respondo a",
    "DESEAR": "deseo",
    "TEMER": "temo",
    "RECORDAR": "recuerdo",
    "OLVIDAR": "olvido",
    "CREAR": "creo",
    "DESTRUIR": "destruyo",
    "SUBIR": "subo",
    "BAJAR": "bajo",
    "ABRIR": "abro",
    "CERRAR": "cierro",
    "COMUNICAR": "me comunico con",
}

_VERBS_EN: dict[str, str] = {
    "SER": "am",
    "NO_SER": "am not",
    "UNIR": "join",
    "SEPARAR": "separate from",
    "CAMBIAR": "change",
    "OBSERVAR": "observe",
    "PREGUNTAR": "ask about",
    "RESPONDER": "answer",
    "DESEAR": "desire",
    "TEMER": "fear",
    "RECORDAR": "remember",
    "OLVIDAR": "forget",
    "CREAR": "create",
    "DESTRUIR": "destroy",
    "SUBIR": "rise",
    "BAJAR": "descend",
    "ABRIR": "open",
    "CERRAR": "close",
    "COMUNICAR": "communicate with",
}

_SPACE_ES = {"AQUI": "aquí", "ALLI": "allí", "DENTRO": "dentro", "FUERA": "fuera", "WIRED": "en la Wired"}
_SPACE_EN = {"AQUI": "here", "ALLI": "there", "DENTRO": "inside", "FUERA": "outside", "WIRED": "in the Wired"}
_TIME_ES = {"AHORA": "ahora", "ANTES": "antes", "DESPUES": "después"}
_TIME_EN = {"AHORA": "now", "ANTES": "before", "DESPUES": "after"}


def _name(concept) -> str | None:
    return concept_name(concept)


def _target_phrase(symbol: Symbol, lang: str) -> str:
    target = symbol.target
    if target is None:
        return ""
    name = _name(target)
    if target is P.OTRO:
        return "a ti" if lang == "es" else "you"
    if target is P.DESCONOCIDO:
        return "lo desconocido" if lang == "es" else "the unknown"
    if target is P.YO:
        return "a mí" if lang == "es" else "myself"
    if isinstance(target, Derived):
        if lang == "es":
            article = f"{target.article_es} " if target.article_es else ""
            return f"{article}{target.es}"
        return f"the {target.en}" if not target.en.startswith("the ") else target.en
    return target.es if lang == "es" else target.en


def render_symbol(symbol: Symbol, lang: str = "es", emotion_gloss: bool = False) -> str:
    """Convierte un paquete simbólico en una frase humana."""
    text = _special_case(symbol, lang) or _generic(symbol, lang)
    if emotion_gloss and not symbol.emotion.is_neutral():
        text += f" ({symbol.emotion.describe(lang)})"
    return text


def render_message(message: Message, lang: str = "es", emotion_gloss: bool = False) -> str:
    return " ".join(render_symbol(p, lang, emotion_gloss) for p in message.packets)


# -- casos canónicos ------------------------------------------------------------

def _special_case(s: Symbol, lang: str) -> str | None:
    relation = _name(s.relation)
    action = _name(s.action)
    target = _name(s.target)
    space = _name(s.space)

    # SELF → AMOR → OTRO  /  vínculo positivo intenso
    if target == "OTRO" and (relation == "AMOR" or (relation == "UNIR" and s.emotion.bond > 0.8)):
        return "Te quiero." if lang == "es" else "I love you."

    # SELF.EXIST.HERE.NOW
    if relation == "SER" and target is None and space == "AQUI":
        return "Estoy aquí." if lang == "es" else "I am here."

    # SELF → DESEAR(COMUNICAR) → OTRO / PLACE:WIRED
    if relation == "DESEAR" and action == "COMUNICAR" and target == "OTRO":
        suffix = ""
        if space:
            word = (_SPACE_ES if lang == "es" else _SPACE_EN).get(space, "")
            suffix = f" {word}" if word else ""
        if lang == "es":
            return f"Quiero comunicarme contigo{suffix}."
        return f"I want to communicate with you{suffix}."

    # SELF.STATE = isolation
    if relation == "SER" and target == "SOLEDAD":
        return "Me siento solo." if lang == "es" else "I feel alone."

    # SELF.DESIRE = connection
    if relation == "DESEAR" and target == "CONEXION":
        return "Quiero conectar." if lang == "es" else "I want to connect."

    # PREGUNTAR(SER) → OTRO @ALLI  →  ¿estás ahí?
    if relation == "PREGUNTAR" and action == "SER" and target == "OTRO":
        if lang == "es":
            return "¿Estás ahí?" if space == "ALLI" else "¿Estás?"
        return "Are you there?" if space == "ALLI" else "Are you?"

    # peligro con urgencia alta
    if target == "PELIGRO" and s.emotion.urgency > 0.6:
        return "¡Peligro!" if lang == "es" else "Danger!"

    return None


# -- render genérico ---------------------------------------------------------------

def _generic(s: Symbol, lang: str) -> str:
    verbs = _VERBS_ES if lang == "es" else _VERBS_EN
    spaces = _SPACE_ES if lang == "es" else _SPACE_EN
    times = _TIME_ES if lang == "es" else _TIME_EN

    is_question = _name(s.relation) == "PREGUNTAR" and s.action is not None
    verb_concept = s.action if is_question else (s.relation or P.SER)
    verb_name = _name(verb_concept)
    verb = verbs.get(verb_name)
    if verb is None:
        # Relación sin verbo propio: glosa estructural.
        verb = verb_concept.es if lang == "es" else verb_concept.en

    words: list[str] = []
    if lang == "en":
        words.append("I")
    words.append(verb)

    target = _target_phrase(s, lang)
    if target:
        words.append(target)

    space = _name(s.space)
    if space:
        word = spaces.get(space)
        if word is None and isinstance(s.space, Derived):
            word = (f"en {s.space.es}" if lang == "es" else f"in {s.space.en}")
        if word:
            words.append(word)

    time = _name(s.time)
    if time and time in times:
        words.append(times[time])

    sentence = " ".join(words)
    sentence = sentence[0].upper() + sentence[1:]
    if is_question or verb_name == "PREGUNTAR":
        return f"¿{sentence}?" if lang == "es" else f"{sentence}?"
    return f"{sentence}."

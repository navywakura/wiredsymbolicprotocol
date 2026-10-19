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

# Segunda persona: cuando el origen del paquete es OTRO (el caso normal al
# escuchar a un interlocutor ajeno, no al hablar nosotros).
_VERBS_ES_2P: dict[str, str] = {
    "SER": "estás",
    "NO_SER": "no estás",
    "UNIR": "te unes a",
    "SEPARAR": "te separas de",
    "CAMBIAR": "cambias",
    "OBSERVAR": "observas",
    "PREGUNTAR": "preguntas por",
    "RESPONDER": "respondes a",
    "DESEAR": "deseas",
    "TEMER": "temes",
    "RECORDAR": "recuerdas",
    "OLVIDAR": "olvidas",
    "CREAR": "creas",
    "DESTRUIR": "destruyes",
    "SUBIR": "subes",
    "BAJAR": "bajas",
    "ABRIR": "abres",
    "CERRAR": "cierras",
    "COMUNICAR": "te comunicas con",
}

_VERBS_EN_2P: dict[str, str] = {
    "SER": "are",
    "NO_SER": "are not",
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
        # «me observas» frente a «me observo»: depende de quién habla
        if _name(symbol.source) == "OTRO":
            return "a mí" if lang == "es" else "me"
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
    source = _name(s.source)

    # ausencia: el otro no está (único caso canónico con origen OTRO)
    if relation == "NO_SER" and source == "OTRO":
        if lang == "es":
            return "No estás aquí." if space == "AQUI" else "No estás."
        return "You are not here." if space == "AQUI" else "You are not."

    # El resto de casos canónicos están escritos en primera persona: si habla
    # otro, se delega en el render genérico, que conjuga en segunda persona.
    if source == "OTRO":
        return None

    # YO → UNIR → OTRO @AQUI  /  unión presente y compartida
    if relation == "UNIR" and target == "OTRO" and space == "AQUI":
        return "Estamos juntos." if lang == "es" else "We are together."

    # SELF → AMOR → OTRO  /  vínculo positivo intenso
    if target == "OTRO" and (relation == "AMOR" or (relation == "UNIR" and s.emotion.bond > 0.8)):
        return "Te quiero." if lang == "es" else "I love you."

    # la transmisión: negación sobre el temor, dirigida a lo desconocido
    if relation == "NO_SER" and action == "TEMER":
        return "No temas lo desconocido." if lang == "es" else "Do not fear the unknown."

    # el saludo de contacto: existencia que busca un vínculo aquí
    if relation == "SER" and action == "BUSCAR" and target == "CONEXION":
        if lang == "es":
            return "Existo y busco un vínculo aquí."
        return "I exist and I seek a bond here."

    # miedo sin objeto conocido
    if relation == "TEMER" and target == "DESCONOCIDO" and s.emotion.valence < 0:
        return "Tengo miedo." if lang == "es" else "I am afraid."

    # memoria del otro
    if relation == "RECORDAR" and target == "OTRO":
        return "Te recuerdo." if lang == "es" else "I remember you."

    # deseo directo hacia el otro
    if relation == "DESEAR" and target == "OTRO" and action is None:
        return "Te deseo." if lang == "es" else "I desire you."

    # separación / despedida
    if relation == "SEPARAR" and target == "OTRO":
        return "Adiós." if lang == "es" else "Goodbye."

    # la pregunta por la realidad (conciencia)
    if relation == "PREGUNTAR" and target == "CONCIENCIA":
        return "¿Qué es real?" if lang == "es" else "What is real?"

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

    # PREGUNTAR(SER) → OTRO: con lugar es presencia, sin lugar es identidad
    if relation == "PREGUNTAR" and action == "SER" and target == "OTRO":
        if lang == "es":
            return "¿Estás ahí?" if space == "ALLI" else "¿Quién eres?"
        return "Are you there?" if space == "ALLI" else "Who are you?"

    # peligro con urgencia alta
    if target == "PELIGRO" and s.emotion.urgency > 0.6:
        return "¡Peligro!" if lang == "es" else "Danger!"

    return None


# -- plano científico como frase ------------------------------------------------------

def _science_phrase(symbol: Symbol, lang: str) -> str:
    """Convierte la carga científica del paquete en sintagma legible.

    «la masa del carbono = 12.011». El protocolo transporta Z y una
    mantisa entera; esto es solo su máscara humana.
    """
    from .primitives_science import Dimension, Element, Quantity, SciPrimitive

    science = symbol.meta.get("science") or {}
    if not science:
        return ""

    magnitudes = []
    for name in science.get("atoms", []):
        atom = SciPrimitive.lookup(name)
        if atom is not None:
            magnitudes.append(atom.es if lang == "es" else atom.en)

    element = science.get("element")
    element_name = Element(int(element)).name(lang) if element is not None else ""

    if magnitudes and element_name:
        head = ", ".join(magnitudes)
        phrase = f"la {head} del {element_name}" if lang == "es" else f"the {head} of {element_name}"
    elif magnitudes:
        head = ", ".join(magnitudes)
        phrase = f"la {head}" if lang == "es" else f"the {head}"
    elif element_name:
        phrase = f"el {element_name}" if lang == "es" else element_name
    else:
        phrase = ""

    spec = science.get("quantity")
    if spec:
        quantity = Quantity(
            int(spec["mantissa"]),
            int(spec.get("exponent", 0)),
            Dimension(*spec.get("dimension", [0] * 7)),
        )
        phrase = f"{phrase} = {quantity.notation()}" if phrase else quantity.notation()
    return phrase


# -- render genérico ---------------------------------------------------------------

def _generic(s: Symbol, lang: str) -> str:
    # El origen decide la persona: hablamos nosotros (YO) o nos habla otro.
    second_person = _name(s.source) == "OTRO"
    if second_person:
        verbs = _VERBS_ES_2P if lang == "es" else _VERBS_EN_2P
    else:
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
        words.append("you" if second_person else "I")

    # En español el pronombre átono precede al verbo: «me observas», «te observo».
    # Solo con verbos simples: los que ya traen pronombre o preposición
    # («te unes a», «respondo a») piden el pronombre tónico detrás.
    clitic = ""
    if lang == "es" and " " not in verb:
        if second_person and _name(s.target) == "YO":
            clitic = "me"
        elif not second_person and _name(s.target) == "OTRO":
            clitic = "te"
    if clitic:
        words.append(clitic)
    words.append(verb)

    target = "" if clitic else _target_phrase(s, lang)  # el clítico ya lo dice
    if target:
        # el verbo puede traer ya su preposición: «respondo a» + «a ti»,
        # «pregunto por» + «a ti» → una sola preposición, la del verbo
        prepositions = ("a", "por", "de", "con", "about", "with", "from", "to")
        tail = verb.rsplit(" ", 1)[-1] if " " in verb else ""
        head = target.split(" ", 1)[0]
        if tail in prepositions and head in prepositions:
            target = target.split(" ", 1)[1] if " " in target else target
        words.append(target)

    # Sin destino, la carga científica ES el objeto y va justo tras el verbo.
    science = _science_phrase(s, lang)
    if science and not (target or clitic):
        words.append(science)
        science = ""

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

    # Con destino, la carga científica cierra la frase como aposición.
    if science:
        words.append(f"— {science}")

    sentence = " ".join(words)
    sentence = sentence[0].upper() + sentence[1:]
    if is_question or verb_name == "PREGUNTAR":
        return f"¿{sentence}?" if lang == "es" else f"{sentence}?"
    return f"{sentence}."

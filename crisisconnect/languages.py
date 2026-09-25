"""Supported speech languages and fixed, non-confidential reply translations."""
from dataclasses import dataclass
import re

from .config import SafeError


LANGUAGES = {"en": "English", "es": "Español", "bn": "বাংলা"}
AZURE_VOICES = {"es": "es-ES-ElviraNeural", "bn": "bn-BD-NabanitaNeural"}


@dataclass(frozen=True)
class SpeechTurn:
    text: str  # English interpretation for the existing workflow, never spoken to the user.
    language: str


def supported_language(language):
    code = str(language).lower().split("-")[0]
    if code not in LANGUAGES:
        raise SafeError("That language is not supported yet. Please use English, Spanish, or Bengali.")
    return code


# Proper place names are inserted unchanged into the two location templates below.
PROMPTS = {
    "Hi, I'm CrisisConnect. This is a local practice conversation. How are you feeling today?": (
        "Hola, soy CrisisConnect. Esta es una conversación de práctica local. ¿Cómo te sientes hoy?",
        "হ্যালো, আমি ক্রাইসিস কানেক্ট। এটি আপনার যন্ত্রে চলা একটি অনুশীলন কথোপকথন। আজ আপনার কেমন লাগছে?"),
    "Thank you for chatting. I am here if you need me.": (
        "Gracias por conversar. Estoy aquí si me necesitas.", "কথা বলার জন্য ধন্যবাদ। প্রয়োজন হলে আমি এখানেই আছি।"),
    "I'm sorry this feels difficult. I'm here to listen. What is your biggest concern right now?": (
        "Siento que estés pasando por un momento difícil. Estoy aquí para escucharte. ¿Qué es lo que más te preocupa ahora?",
        "আপনার জন্য সময়টা কঠিন যাচ্ছে শুনে খারাপ লাগছে। আমি আপনার কথা শুনছি। এই মুহূর্তে আপনার সবচেয়ে বড় চিন্তা কী?"),
    "That sounds difficult. Do you have somewhere safe to stay? Please keep your answer general.": (
        "Eso suena difícil. ¿Tienes un lugar seguro donde quedarte? Responde de forma general.",
        "পরিস্থিতিটা কঠিন মনে হচ্ছে। আপনার কি নিরাপদে থাকার কোনো জায়গা আছে? সাধারণভাবে উত্তর দিন।"),
    "I hear that basic supplies are a concern. Is someone nearby able to support you?": (
        "Entiendo que te preocupan los suministros básicos. ¿Hay alguien cerca que pueda apoyarte?",
        "বুঝতে পারছি, নিত্যপ্রয়োজনীয় জিনিস নিয়ে আপনার চিন্তা হচ্ছে। কাছাকাছি কেউ কি আপনাকে সাহায্য করতে পারবেন?"),
    "Hello! I'm here to listen. What would you like to talk about?": (
        "¡Hola! Estoy aquí para escucharte. ¿De qué te gustaría hablar?", "হ্যালো! আমি আপনার কথা শুনছি। আপনি কী নিয়ে কথা বলতে চান?"),
    "You're welcome. Would you like to talk about anything else? Say goodbye when you want to finish.": (
        "De nada. ¿Te gustaría hablar de algo más? Di adiós cuando quieras terminar.",
        "আপনাকে স্বাগতম। আপনি কি আর কিছু নিয়ে কথা বলতে চান? শেষ করতে চাইলে বিদায় বলুন।"),
    "I'm glad to hear that. What would you like to talk about today?": (
        "Me alegra oírlo. ¿De qué te gustaría hablar hoy?", "শুনে ভালো লাগল। আজ আপনি কী নিয়ে কথা বলতে চান?"),
    "In this demo I can listen and ask simple follow-up questions. I don't check disasters or arrange assistance. What would you like to discuss?": (
        "En esta demostración puedo escucharte y hacer preguntas sencillas. No verifico desastres ni gestiono ayuda. ¿De qué te gustaría hablar?",
        "এই ডেমোতে আমি আপনার কথা শুনতে এবং সহজ প্রশ্ন করতে পারি। আমি দুর্যোগ যাচাই করি না বা সহায়তার ব্যবস্থা করি না। আপনি কী নিয়ে আলোচনা করতে চান?"),
    "I'm listening. What kind of support would help you most right now?": (
        "Te escucho. ¿Qué tipo de apoyo te ayudaría más ahora?", "আমি শুনছি। এই মুহূর্তে কোন ধরনের সহায়তা আপনার সবচেয়ে বেশি কাজে আসবে?"),
    "Thank you for sharing. Is there anything else you would like to talk about? Please leave out private details.": (
        "Gracias por compartirlo. ¿Hay algo más de lo que quieras hablar? No incluyas datos privados.",
        "কথাগুলো বলার জন্য ধন্যবাদ। আপনি কি আর কিছু নিয়ে কথা বলতে চান? ব্যক্তিগত গোপন তথ্য বলবেন না।"),
    "Are you okay? Please say yes or no.": (
        "¿Estás bien? Por favor, di sí o no.", "আপনি কি ঠিক আছেন? দয়া করে হ্যাঁ বা না বলুন।"),
    "I am here if you need me.": ("Estoy aquí si me necesitas.", "প্রয়োজন হলে আমি এখানেই আছি।"),
    "I'm here if you need me.": ("Estoy aquí si me necesitas.", "প্রয়োজন হলে আমি এখানেই আছি।"),
    "What town or city and state are you in? Please say just the place names, not your address.": (
        "¿En qué pueblo o ciudad y estado estás? Di solo los nombres de los lugares, no tu dirección.",
        "আপনি কোন শহরে এবং কোন রাজ্যে আছেন? শুধু জায়গার নাম বলুন, আপনার ঠিকানা নয়।"),
    "I want to make sure I understood. Are you okay? Please say yes or no.": (
        "Quiero asegurarme de haber entendido. ¿Estás bien? Di sí o no.",
        "আমি ঠিক বুঝেছি কি না নিশ্চিত হতে চাই। আপনি কি ঠিক আছেন? হ্যাঁ বা না বলুন।"),
    "I couldn't identify that town and state.": ("No pude identificar ese pueblo y estado.", "শহর ও রাজ্যটি শনাক্ত করতে পারিনি।"),
    "Let's correct the location.": ("Vamos a corregir la ubicación.", "আসুন, জায়গার নামটি ঠিক করে নিই।"),
    "The device location is more than ten kilometers from the town's reference point.": (
        "La ubicación del dispositivo está a más de diez kilómetros del punto de referencia de la ciudad.",
        "যন্ত্রের অবস্থান শহরের নির্ধারিত বিন্দু থেকে দশ কিলোমিটারের বেশি দূরে।"),
    "Device location is turned off.": ("La ubicación del dispositivo está desactivada.", "যন্ত্রের অবস্থান সেবা বন্ধ আছে।"),
    "The app does not have permission to read your location.": (
        "La aplicación no tiene permiso para consultar tu ubicación.", "অ্যাপের আপনার অবস্থান জানার অনুমতি নেই।"),
    "I couldn't get a reliable device location.": (
        "No pude obtener una ubicación fiable del dispositivo.", "যন্ত্রের নির্ভরযোগ্য অবস্থান পাওয়া যায়নি।"),
    "You can enable location in device settings and say check again, or say continue without it.": (
        "Puedes activar la ubicación en los ajustes del dispositivo y decir comprobar otra vez, o decir continuar sin ella.",
        "যন্ত্রের সেটিংসে অবস্থান সেবা চালু করে আবার দেখুন বলতে পারেন, অথবা এটি ছাড়া চালিয়ে যেতে চালিয়ে যান বলুন।"),
    "Turn on location in your device settings and say check again, or say continue to use the town you gave me.": (
        "Activa la ubicación en los ajustes y di comprobar otra vez, o di continuar para usar la ciudad que me has indicado.",
        "যন্ত্রের সেটিংসে অবস্থান সেবা চালু করে আবার দেখুন বলুন, অথবা আপনার বলা শহর ব্যবহার করতে চালিয়ে যান বলুন।"),
    "I'm sorry, I couldn't confirm your location. We can try again another time. I am here if you need me.": (
        "Lo siento, no pude confirmar tu ubicación. Podemos intentarlo en otro momento. Estoy aquí si me necesitas.",
        "দুঃখিত, আপনার অবস্থান নিশ্চিত করতে পারিনি। আমরা অন্য সময় আবার চেষ্টা করতে পারি। প্রয়োজন হলে আমি এখানেই আছি।"),
    "I couldn't find a recent FEMA disaster declaration for that area. This does not mean the area is safe. I'll end this conversation here. I am here if you need me.": (
        "No encontré una declaración reciente de desastre de FEMA para esa zona. Eso no significa que la zona sea segura. Terminaré esta conversación aquí. Estoy aquí si me necesitas.",
        "ওই এলাকার জন্য ফেমার সাম্প্রতিক দুর্যোগ ঘোষণা পাইনি। এর অর্থ এই নয় যে এলাকাটি নিরাপদ। এই কথোপকথন এখানেই শেষ করছি। প্রয়োজন হলে আমি এখানেই আছি।"),
    "Thank you for talking with me. I am here if you need me.": (
        "Gracias por hablar conmigo. Estoy aquí si me necesitas.", "আমার সঙ্গে কথা বলার জন্য ধন্যবাদ। প্রয়োজন হলে আমি এখানেই আছি।"),
    "How is the disaster affecting you right now? Please keep it general and leave out personal details.": (
        "¿Cómo te está afectando el desastre ahora? Habla de forma general y no incluyas datos personales.",
        "এই মুহূর্তে দুর্যোগটি আপনার ওপর কীভাবে প্রভাব ফেলছে? সাধারণভাবে বলুন, ব্যক্তিগত তথ্য দেবেন না।"),
    "Do you have somewhere safe to stay?": ("¿Tienes un lugar seguro donde quedarte?", "আপনার কি নিরাপদে থাকার কোনো জায়গা আছে?"),
    "Do you have access to food and drinking water?": ("¿Tienes acceso a comida y agua potable?", "আপনি কি খাবার ও পানীয় জল পাচ্ছেন?"),
    "Are you alone, or are other people with you? Please do not share their names.": (
        "¿Estás a solas o hay otras personas contigo? No digas sus nombres.", "আপনি কি একা, নাকি অন্যরাও আপনার সঙ্গে আছেন? তাঁদের নাম বলবেন না।"),
    "What kind of practical support would help you most right now?": (
        "¿Qué tipo de apoyo práctico te ayudaría más ahora?", "এই মুহূর্তে কোন ধরনের বাস্তব সহায়তা আপনার সবচেয়ে বেশি কাজে আসবে?"),
    "Is there anything else about the situation you would like to discuss, without sharing private information?": (
        "¿Hay algo más de la situación que quieras comentar, sin compartir información privada?",
        "গোপন তথ্য না দিয়ে পরিস্থিতি সম্পর্কে আপনি কি আর কিছু আলোচনা করতে চান?"),
}


def localize(text, language):
    language = supported_language(language)
    if language == "en":
        return text
    index = 0 if language == "es" else 1
    if text in PROMPTS:
        return PROMPTS[text][index]
    templates = (
        (r"I heard (.+)\. Is that the location you mean\? Please say yes or no\.",
         ("He oído {place}. ¿Es ese el lugar que quieres indicar? Di sí o no.", "আমি শুনেছি {place}। আপনি কি এই জায়গার কথা বলছেন? হ্যাঁ বা না বলুন।")),
        (r"Is (.+) correct\? Please say yes or no\.",
         ("¿Es correcto {place}? Di sí o no.", "{place} কি ঠিক? হ্যাঁ বা না বলুন।")),
    )
    for pattern, translations in templates:
        match = re.fullmatch(pattern, text)
        if match:
            return translations[index].format(place=match[1])
    # Location retry and availability prompts concatenate two reviewed phrases.
    for source in sorted(PROMPTS, key=len, reverse=True):
        if text.startswith(source + " "):
            return PROMPTS[source][index] + " " + localize(text[len(source)+1:], language)
    raise SafeError("This reply has no translation for the detected language. Please restart the conversation.")

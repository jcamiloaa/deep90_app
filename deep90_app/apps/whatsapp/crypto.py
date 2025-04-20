"""
Utilidades de criptografía para WhatsApp Flows.

Este módulo proporciona funciones para cifrar y descifrar datos
de acuerdo con los requisitos de seguridad de WhatsApp Flows.
"""

import json
import os
from base64 import b64decode, b64encode
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1, hashes
from cryptography.hazmat.primitives.ciphers import algorithms, Cipher, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def get_private_key():
    """
    Obtiene la clave privada RSA desde el archivo especificado en las variables de entorno.
    
    Returns:
        La clave privada cargada
    """
    # Intentar obtener la ruta al archivo de clave privada desde las variables de entorno
    private_key_path = os.environ.get('WHATSAPP_PRIVATE_KEY_PATH')
    
    # Si no está en las variables de entorno, intentar desde settings
    if not private_key_path:
        private_key_path = getattr(settings, 'WHATSAPP_PRIVATE_KEY_PATH', None)
        
    if not private_key_path:
        raise ValueError("No se ha configurado la ruta a la clave privada para WhatsApp Flows (WHATSAPP_PRIVATE_KEY_PATH)")
    
    try:
        # Leer el contenido del archivo de clave privada
        logger.debug(f"Intentando leer la clave privada desde: {private_key_path}")
        with open(private_key_path, 'rb') as key_file:
            private_key_data = key_file.read()
            
        # Cargar la clave privada desde el contenido
        return load_pem_private_key(private_key_data, password=None)
    except FileNotFoundError:
        logger.error(f"No se pudo encontrar el archivo de clave privada en: {private_key_path}")
        raise ValueError(f"Archivo de clave privada no encontrado: {private_key_path}")
    except Exception as e:
        logger.error(f"Error al cargar la clave privada: {str(e)}")
        raise ValueError(f"Error al cargar la clave privada: {str(e)}")


def decrypt_request(encrypted_flow_data_b64, encrypted_aes_key_b64, initial_vector_b64):
    """
    Descifra los datos del flujo de WhatsApp.
    
    Args:
        encrypted_flow_data_b64: Datos del flujo cifrados en base64
        encrypted_aes_key_b64: Clave AES cifrada en base64
        initial_vector_b64: Vector de inicialización en base64
    
    Returns:
        Una tupla con (datos_descifrados, clave_aes, vector_inicializacion)
    """
    flow_data = b64decode(encrypted_flow_data_b64)
    iv = b64decode(initial_vector_b64)

    # Descifrar la clave AES de cifrado
    encrypted_aes_key = b64decode(encrypted_aes_key_b64)
    private_key = get_private_key()
    aes_key = private_key.decrypt(
        encrypted_aes_key, 
        OAEP(
            mgf=MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    # Descifrar los datos del flujo
    encrypted_flow_data_body = flow_data[:-16]
    encrypted_flow_data_tag = flow_data[-16:]
    decryptor = Cipher(
        algorithms.AES(aes_key),
        modes.GCM(iv, encrypted_flow_data_tag)
    ).decryptor()
    
    decrypted_data_bytes = decryptor.update(encrypted_flow_data_body) + decryptor.finalize()
    decrypted_data = json.loads(decrypted_data_bytes.decode("utf-8"))
    
    return decrypted_data, aes_key, iv


def _remove_proxies(obj):
    """
    Convierte objetos __proxy__ (traducciones perezosas) a str recursivamente en un dict/list.
    """
    from django.utils.functional import Promise
    if isinstance(obj, dict):
        return {k: _remove_proxies(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_remove_proxies(i) for i in obj]
    elif isinstance(obj, Promise):
        return str(obj)
    return obj


def encrypt_response(response, aes_key, iv):
    """
    Cifra la respuesta para enviar a WhatsApp Flows.
    
    Args:
        response: Diccionario con la respuesta (sin traducciones, solo en español)
        aes_key: Clave AES
        iv: Vector de inicialización
    
    Returns:
        Datos cifrados en formato base64
    """
    # Elimina traducciones perezosas y deja todo en español
    response = _remove_proxies(response)
    
    # Voltear el vector de inicialización
    flipped_iv = bytearray()
    for byte in iv:
        flipped_iv.append(byte ^ 0xFF)

    # Cifrar los datos de respuesta
    encryptor = Cipher(
        algorithms.AES(aes_key),
        modes.GCM(flipped_iv)
    ).encryptor()
    
    return b64encode(
        encryptor.update(json.dumps(response, ensure_ascii=False).encode("utf-8")) +
        encryptor.finalize() +
        encryptor.tag
    ).decode("utf-8")
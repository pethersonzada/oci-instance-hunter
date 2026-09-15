import os
import time
import oci
from oci.core import ComputeClient
from oci.core.models import (
    LaunchInstanceDetails,
    CreateVnicDetails
)

config = {
    "user": os.getenv("OCI_USER"),
    "key_content": os.getenv("OCI_PRIVATE_KEY"),
    "fingerprint": os.getenv("OCI_FINGERPRINT"),
    "tenancy": os.getenv("OCI_TENANCY"),
    "region": os.getenv("OCI_REGION", "sa-saopaulo-1")
}

compartment_id = os.getenv("OCI_COMPARTMENT")
subnet_id = os.getenv("OCI_SUBNET_ID")
ssh_pub_key = os.getenv("SSH_PUBLIC_KEY")

SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "45"))
MAX_RUNTIME_SECONDS = int(os.getenv("MAX_RUNTIME_SECONDS", "21000"))

compute_client = ComputeClient(config)

# Codes que significam "isso nunca vai dar certo, tentando de novo".
# Tudo que NÃO estiver aqui e tratado como retryable.
FATAL_CODES = {
    "NotAuthenticated",       # credencial errada
    "NotAuthorized",          # sem permissão no compartment/policy
    "InvalidParameter",       # parametro tipo AD errado, subnet errada
    "LimitExceeded",          # estourou quota da tier free
    "QuotaExceeded",
    "TenantIsOnPaymentHold",
}


def get_image_id():
    images = compute_client.list_images(
        compartment_id=compartment_id,
        operating_system="Canonical Ubuntu",
        operating_system_version="22.04",
        shape="VM.Standard.A1.Flex",
        sort_by="TIMECREATED",
        sort_order="DESC"
    ).data

    if not images:
        print("Nenhuma imagem encontrada. Abortando.")
        exit(1)

    return images[0].id


def try_launch_instance(image_id):
    launch_details = LaunchInstanceDetails(
        compartment_id=compartment_id,
        availability_domain="DOBJ:SA-SAOPAULO-1-AD-1",
        shape="VM.Standard.A1.Flex",
        shape_config={
            "ocpus": 4.0,
            "memory_in_gbs": 24.0
        },
        display_name="instance-hunter-auto",
        image_id=image_id,
        create_vnic_details=CreateVnicDetails(
            subnet_id=subnet_id,
            assign_public_ip=True
        ),
        metadata={
            "ssh_authorized_keys": ssh_pub_key
        }
    )

    response = compute_client.launch_instance(launch_details)
    return response.data.id


def get_backoff_seconds(e):
    if e.status == 429 or e.code == "TooManyRequests":
        return SLEEP_SECONDS * 6

    if e.status >= 500:
        return SLEEP_SECONDS

    # qualquer outro retryable nao mapeado: espera um pouco mais,
    # por seguranca, ja que nao sabemos a causa exata
    return SLEEP_SECONDS * 3


def main():
    image_id = get_image_id()
    print(f"Imagem do Ubuntu encontrada: {image_id}")

    start = time.time()
    tentativa = 0

    while time.time() - start < MAX_RUNTIME_SECONDS:
        tentativa += 1
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            instance_id = try_launch_instance(image_id)
            print(f"[{timestamp}] SUCESSO ABSOLUTO! Instancia criada: {instance_id}")
            exit(0)

        except oci.exceptions.ServiceError as e:
            if e.code in FATAL_CODES:
                print(f"[{timestamp}] Erro FATAL da API da OCI "
                      f"(status={e.status}, code={e.code}): {e.message}")
                print("Esse erro nao se resolve tentando de novo. Corrija a causa e reinicie.")
                exit(1)

            backoff = get_backoff_seconds(e)
            print(f"[{timestamp}] Tentativa {tentativa}: erro retryable "
                  f"(status={e.status}, code={e.code}) -> '{e.message}'. "
                  f"Aguardando {backoff}s...")
            time.sleep(backoff)

        except Exception as e:
            # erro nao-OCI (rede, timeout, etc): tambem retryable, com espera padrao
            print(f"[{timestamp}] Tentativa {tentativa}: erro inesperado nao-OCI: {e}. "
                  f"Aguardando {SLEEP_SECONDS}s...")
            time.sleep(SLEEP_SECONDS)

    print("Tempo máximo de execucao atingido sem sucesso. O workflow sera reanimado no proximo agendamento.")


if __name__ == "__main__":
    main()

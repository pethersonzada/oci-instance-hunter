import os
import time
import sys
import oci
from oci.core import ComputeClient
from oci.identity import IdentityClient
from oci.core.models import (
    LaunchInstanceDetails,
    CreateVnicDetails,
    InstanceShapeConfigDetails
)

REQUIRED_ENVS = ["OCI_USER", "OCI_PRIVATE_KEY", "OCI_FINGERPRINT", "OCI_TENANCY", "OCI_COMPARTMENT", "OCI_SUBNET_ID", "SSH_PUBLIC_KEY"]
missing_envs = [var for var in REQUIRED_ENVS if not os.getenv(var)]
if missing_envs:
    print(f"Erro: As seguintes variáveis de ambiente estão em falta: {', '.join(missing_envs)}")
    sys.exit(1)

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

OCPUS = float(os.getenv("OCI_OCPUS", "2.0"))
MEMORY_GBS = float(os.getenv("OCI_MEMORY_GBS", "12.0"))

SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "45"))
MAX_RUNTIME_SECONDS = int(os.getenv("MAX_RUNTIME_SECONDS", "21000"))

compute_client = ComputeClient(config)

FATAL_CODES = {
    "NotAuthenticated",
    "NotAuthorized",
    "InvalidParameter",
    "TenantIsOnPaymentHold",
}


def get_availability_domain():
    try:
        identity_client = IdentityClient(config)
        ads = identity_client.list_availability_domains(compartment_id=compartment_id).data
        if ads:
            return ads[0].name
    except Exception as e:
        print(f"Aviso: Não foi possível obter o AD via API ({e}). A utilizar o valor por omissão.")
    return "DOBJ:SA-SAOPAULO-1-AD-1"


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
        print("Erro: Nenhuma imagem do Ubuntu 22.04 encontrada para VM.Standard.A1.Flex.")
        sys.exit(1)

    return images[0].id


def try_launch_instance(image_id, availability_domain):
    shape_config = InstanceShapeConfigDetails(
        ocpus=OCPUS,
        memory_in_gbs=MEMORY_GBS
    )

    vnic_details = CreateVnicDetails(
        subnet_id=subnet_id,
        assign_public_ip=True
    )

    launch_details = LaunchInstanceDetails(
        compartment_id=compartment_id,
        availability_domain=availability_domain,
        shape="VM.Standard.A1.Flex",
        shape_config=shape_config,
        display_name="instance-hunter-auto",
        image_id=image_id,
        create_vnic_details=vnic_details,
        metadata={
            "ssh_authorized_keys": ssh_pub_key
        }
    )

    response = compute_client.launch_instance(launch_details)
    return response.data.id


def get_backoff_seconds(e):
    if e.status == 429 or e.code == "TooManyRequests":
        return SLEEP_SECONDS * 4

    if e.status >= 500:
        return SLEEP_SECONDS

    return SLEEP_SECONDS * 2


def main():
    ad_name = get_availability_domain()
    image_id = get_image_id()
    
    print(f"--- Inicialização do OCI Hunter ---")
    print(f"Região: {config['region']} | AD: {ad_name}")
    print(f"Imagem Ubuntu ID: {image_id}")
    print(f"Configuração Solicitada: {OCPUS} OCPUs | {MEMORY_GBS} GB RAM")
    print(f"------------------------------------")

    start_time = time.time()
    tentativa = 0

    while time.time() - start_time < MAX_RUNTIME_SECONDS:
        tentativa += 1
        elapsed_min = int((time.time() - start_time) / 60)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            instance_id = try_launch_instance(image_id, ad_name)
            print(f"[{timestamp}] SUCESSO! Instância criada com ID: {instance_id}")
            sys.exit(0)

        except oci.exceptions.ServiceError as e:
            if e.code in FATAL_CODES:
                print(f"[{timestamp}] Erro FATAL da API OCI (Status {e.status}, Código {e.code}): {e.message}")
                print("Execução interrompida por erro irrecuperável.")
                sys.exit(1)

            if e.code in ["LimitExceeded", "QuotaExceeded"]:
                print(f"[{timestamp}] Erro de limite atingido ({e.code}): {e.message}")
                print("Verifique se as especificações (OCPUs/RAM) excedem a quota disponível na conta.")
                sys.exit(1)

            backoff = get_backoff_seconds(e)
            print(f"[{timestamp}] [Tentativa {tentativa} | {elapsed_min}m decorridos] Erro temporário ({e.status} - {e.code}): {e.message}. A aguardar {backoff}s...")
            time.sleep(backoff)

        except Exception as e:
            print(f"[{timestamp}] [Tentativa {tentativa}] Erro não tratado: {e}. A aguardar {SLEEP_SECONDS}s...")
            time.sleep(SLEEP_SECONDS)

    print("Tempo limite de execução atingido sem conseguir alocar capacidade. O script será encerrado.")


if __name__ == "__main__":
    main()

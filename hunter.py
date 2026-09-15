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

SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "30"))
MAX_RUNTIME_SECONDS = int(os.getenv("MAX_RUNTIME_SECONDS", "21000"))

compute_client = ComputeClient(config)


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


def is_capacity_error(e):
    """
    Checa pelo code do erro, que e estavel, em vez de string livre
    da mensagem, que a Oracle pode reformular sem aviso.
    """
    if e.status != 500:
        return False

    if e.code == "InternalError":
        return True

    msg = (e.message or "").lower()
    return "out of" in msg and "capacity" in msg


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
            if is_capacity_error(e):
                print(f"[{timestamp}] Tentativa {tentativa}: sem capacidade "
                      f"(status={e.status}, code={e.code}). Aguardando {SLEEP_SECONDS}s...")
            else:
                print(f"[{timestamp}] Erro inesperado da API da OCI "
                      f"(status={e.status}, code={e.code}): {e.message}")
                exit(1)

        time.sleep(SLEEP_SECONDS)

    print("Tempo maximo de execucao atingido sem sucesso. O workflow sera reanimado no proximo agendamento.")


if __name__ == "__main__":
    main()

import os
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

compute_client = ComputeClient(config)

def try_launch_instance():
    print("Tentando criar a instancia Ampere A1 (4 OCPUs / 24GB)...")
    
    image_client = oci.core.ComputeClient(config)
    images = image_client.list_images(
        compartment_id=compartment_id,
        operating_system="Canonical Ubuntu",
        operating_system_version="22.04",
        shape="VM.Standard.A1.Flex",
        sort_by="TIMECREATED",
        sort_order="DESC"
    ).data
    
    if not images:
        print("Nenhuma imagem encontrada.")
        exit(1)
        
    image_id = images[0].id
    print(f"Imagem do Ubuntu encontrada: {image_id}")

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

    try:
        response = compute_client.launch_instance(launch_details)
        print("SUCESSO ABSOLUTO! Instancia criada:", response.data.id)
        exit(0)
    except oci.exceptions.ServiceError as e:
        if e.status == 500 and "Out of capacity" in e.message:
            print("Sem capacidade no momento. Tentando novamente...")
        else:
            print(f"Erro inesperado da API da OCI: {e}")
            exit(1)

if __name__ == "__main__":
    try_launch_instance()

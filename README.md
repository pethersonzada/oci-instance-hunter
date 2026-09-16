# OCI Instance Hunter

[![GitHub Actions](https://img.shields.io/github/actions/workflow/status/pethersonzada/oci-instance-hunter/hunter.yml?style=flat-square&logo=github-actions&logoColor=white&label=Automation)](https://github.com/pethersonzada/oci-instance-hunter/actions/workflows/hunter.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Oracle Cloud](https://img.shields.io/badge/Oracle%20Cloud-Always%20Free-F80000?style=flat-square&logo=oracle&logoColor=white)](https://www.oracle.com/cloud/)
[![License: MIT](https://img.shields.io/badge/License-MIT-00C7B7?style=flat-square&logo=opensourceinitiative&logoColor=white)](LICENSE)

Automação inteligente construída com Python e GitHub Actions para tentar alocar recorrentemente uma instância na Oracle Cloud Infrastructure (OCI).

## Como Funciona

Como a demanda por instâncias Ampere A1 gratuitas é extremamente alta, as regiões costumam sofrer com escassez de hardware (`Out of host capacity`). Este projeto resolve isso automatizando o processo:

1. Um script em Python utiliza o SDK oficial da OCI para solicitar a criação de uma instância Flex.
2. O **GitHub Actions** dispara o script automaticamente a cada 2 minutos (`cron`).
3. O robô tenta a alocação de forma incansável até que a Oracle libere capacidade na região configurada.

---

## Tecnologias Utilizadas

* **Python 3.10+**
* **Oracle Cloud Infrastructure Python SDK (`oci`)**
* **GitHub Actions** (para orquestração e execução agendada)

---

## Configuração das Secrets no GitHub

Para que o script funcione, você deve configurar as seguintes **Repository Secrets** nas configurações do seu repositório GitHub (`Settings > Secrets and variables > Actions`):

| Nome da Secret | Descrição |
| :--- | :--- |
| `OCI_USER` | OCID do usuário da OCI |
| `OCI_PRIVATE_KEY` | Conteúdo da chave privada PEM gerada para a API |
| `OCI_FINGERPRINT` | Fingerprint da chave da API |
| `OCI_TENANCY` | OCID da tenancy |
| `OCI_REGION` | Região alvo (ex: `sa-saopaulo-1`) |
| `OCI_COMPARTMENT` | OCID do compartment onde a instância será criada |
| `OCI_SUBNET_ID` | OCID da Subnet da VCN |
| `SSH_PUBLIC_KEY` | Chave pública SSH para acesso à máquina |

---

## Agendamento (Cron)

O workflow está configurado no diretório `.github/workflows/hunter.yml` para rodar de 2 em 2 minutos de forma autônoma:

```yaml
on:
  schedule:
    - cron: '*/2 * * * *'
  workflow_dispatch:

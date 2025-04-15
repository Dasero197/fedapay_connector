# FedaPay Connector

FedaPay Connector est un connecteur asynchrone pour interagir avec l'API FedaPay. Il permet de gérer les paiements, les statuts des transactions, et les webhooks.

## Installation

```bash
pip install fedapay_connector

### Utilisation

from fedapay_connector import FedapayConnector, PaiementSetup, UserData, Pays, MethodesPaiement
import asyncio

async def main():
    fedapay = FedapayConnector()
    setup = PaiementSetup(pays=Pays.benin, method=MethodesPaiement.moov)
    client = UserData(nom="john", prenom="doe", email="myemail@domain.com", tel="+22964000001")

    # Initialisation du paiement
    resp = await fedapay.Fedapay_pay(setup=setup, client_infos=client, montant_paiement=1000)
    print(resp)

    # Vérification du statut
    status = await fedapay.Check_Fedapay_status(resp.get("id_transaction_fedapay"))
    print(status)

if __name__ == "__main__":
    asyncio.run(main())

#### Licence

Ce projet est sous licence GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). Consultez le fichier LICENSE pour plus d'informations.


---

### 4. **Ajouter une Mention dans le Code Source**

Ajoutez une mention de la licence AGPL dans les fichiers principaux de votre projet, comme `connector.py`. Cela garantit que les utilisateurs sont informés de la licence lorsqu'ils consultent le code.

#### Exemple d'en-tête dans `connector.py` :
```python
"""
FedaPay Connector

Copyright (C) 2025 ASSOGBA Dayane

Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
conformément aux termes de la GNU Affero General Public License publiée par la
Free Software Foundation, soit la version 3 de la licence, soit (à votre choix)
toute version ultérieure.

Ce programme est distribué dans l'espoir qu'il sera utile,
mais SANS AUCUNE GARANTIE ; sans même la garantie implicite de
COMMERCIALISATION ou D'ADÉQUATION À UN OBJECTIF PARTICULIER.
Consultez la GNU Affero General Public License pour plus de détails.

Vous devriez avoir reçu une copie de la GNU Affero General Public License
avec ce programme. Si ce n'est pas le cas, consultez <https://www.gnu.org/licenses/>.
"""
# Deploy na Oracle Cloud (Free Tier)

Guia para colocar o DOJUFLA no ar **de graça** numa VM ARM (Ampere) da Oracle.
A VM tem RAM de sobra para o `torch`, então roda o projeto como está.

---

## 1. Criar a VM (no console da Oracle)

1. Acesse **cloud.oracle.com** e faça login (a conta "Always Free").
2. Menu **Compute → Instances → Create instance**.
3. Preencha:
   - **Name**: `dojufla`
   - **Image**: `Ubuntu` (Canonical Ubuntu 24.04 ou 22.04)
   - **Shape**: **Ampere / `VM.Standard.A1.Flex`** — defina **2 OCPU** e **12 GB** de RAM
     (o sempre-grátis permite até 4 OCPU / 24 GB).
   - **Networking**: deixe a VCN padrão; marque **Assign a public IPv4 address**.
   - **SSH keys**: **Save private key** (baixe o arquivo `.key`).
4. Clique em **Create**. Anote o **Public IP address** da VM.

> Se aparecer "Out of capacity" para o ARM, tente outra região/AD ou aguarde — é comum.

## 2. Conectar por SSH (do seu Windows)

No PowerShell, na pasta onde salvou a chave:

```powershell
ssh -i .\ssh-key-2026-10-06.key ubuntu@<IP-PUBLICO>
```

(Usuário padrão das imagens Ubuntu da Oracle: `ubuntu`.)

## 3. Liberar as portas 80 e 443 na Oracle (obrigatório)

No console: **Networking → Virtual Cloud Networks → sua VCN → Security Lists →
Default Security List → Add Ingress Rules**, adicione:

| Source CIDR | IP Protocol | Destination Port Range |
| --- | --- | --- |
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

Sem isso a página não abre de fora, mesmo com tudo certo na VM.

## 4. Subir a aplicação (dentro da VM)

Já conectado por SSH:

```bash
git clone https://github.com/Renan2004a/DOJUFLA.git ~/DOJUFLA
cd ~/DOJUFLA
bash deploy/oracle_setup.sh
```

O script instala tudo (Python, venv, Nginx), baixa o modelo, cria o serviço
(systemd) e configura o proxy. Ao final ele avisa para editar o `.env`.

## 5. Colocar sua chave da Groq

```bash
nano ~/DOJUFLA/.env
# edite a linha:  GROQ_API_KEY=sua-chave-aqui
sudo systemctl restart dojufla
```

Teste:

```bash
curl -s http://localhost/healthz   # (não existe; teste a home abaixo)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/
```

## 6. Acessar

Abra no navegador: **http://<IP-PUBLICO>**

Faça login com um usuário existente, ou crie um novo (só que `/register` cria
`usuario`). Para ter um **super_admin**:

```bash
cd ~/DOJUFLA && ./venv/bin/python promover_super_admin.py SEU_USUARIO
```

---

## 7. (Opcional) HTTPS com domínio

Se tiver um domínio apontando para o IP da VM:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d seudominio.com
```

O Certbot configura o HTTPS e a renovação automática.

---

## Atualizar o site depois

```bash
cd ~/DOJUFLA
git pull
./venv/bin/pip install -r requirements.txt
sudo systemctl restart dojufla
```

## Comandos úteis

```bash
sudo systemctl status dojufla      # status
sudo journalctl -u dojufla -f      # logs ao vivo
sudo systemctl restart dojufla     # reiniciar
```

## Observações

- **Banco de dados**: o `database.db` fica na VM (persistente). Faça backup de vez em quando
  (`cp ~/DOJUFLA/database.db ~/backup-$(date +%F).db`).
- **Ram**: com `--workers 1` há só uma cópia do modelo na memória (~1 GB).
- A VM "Always Free" **não é desligada** por inatividade — diferente do Render free.

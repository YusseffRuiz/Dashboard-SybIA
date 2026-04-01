import trustme
# Generamos un certificado "falso" pero criptográficamente válido
ca = trustme.CA()
cert = ca.issue_cert("200.66.78.173", "localhost", "127.0.0.1")

# Guardamos las llaves en tu carpeta Dashboard-SybIA
cert.private_key_pem.write_to_path("key.pem")
cert.cert_chain_pems[0].write_to_path("cert.pem")
exit()
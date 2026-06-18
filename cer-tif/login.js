
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const statusDiv = document.getElementById('login-status');

    loginForm.addEventListener('submit', async (e) => {
        // Empêche le rechargement de la page
        e.preventDefault();

        const identifiant = document.getElementById('identifiant').value;
        const password = document.getElementById('password').value;

        statusDiv.innerText = "> VÉRIFICATION EN COURS...";
        statusDiv.style.color = "var(--text-color)";

        try {
            const reponse = await fetch("/api/connexion", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    identifiant: identifiant,
                    mot_de_passe: password
                })
            });
            const data = await reponse.json();

            if (data.ok) {
                statusDiv.innerText = "> ACCÈS AUTORISÉ. OUVERTURE DE LA SESSION...";
                statusDiv.style.color = "var(--text-color)";
                window.location.href = "index.html";
            } else {
                statusDiv.innerText = "> ERREUR : " + data.message;
                statusDiv.style.color = "red";
                document.getElementById('password').value = "";
                document.getElementById('password').focus();
            }
        } catch (err) {
            statusDiv.innerText = "> ERREUR RÉSEAU : SERVEUR INJOIGNABLE.";
            statusDiv.style.color = "red";
        }
    });
});
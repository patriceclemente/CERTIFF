document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('signup-form');
    const statusDiv = document.getElementById('signup-status');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const username = document.getElementById('username').value;
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;

        statusDiv.innerText = "> CRÉATION DU COMPTE...";
        statusDiv.style.color = "var(--text-color)";

        try {
            const reponse = await fetch("/api/inscription", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: username,
                    email: email,
                    mot_de_passe: password
                })
            });
            const data = await reponse.json();

            if (data.ok) {
                statusDiv.innerText = "> COMPTE CRÉÉ. vérifier vos mails pour pouvoir accéder à votre compte.";
                statusDiv.style.color = "var(--text-color)";
                form.reset();
            } else {
                statusDiv.innerText = "> ERREUR : " + data.message;
                statusDiv.style.color = "red";
            }
        } catch (err) {
            statusDiv.innerText = "> ERREUR " + err.message;
            statusDiv.style.color = "red";
        }
    });
});

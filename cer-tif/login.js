document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const statusDiv = document.getElementById('login-status');

    // Identifiants locaux pour la phase de développement
    const LOCAL_USER = "admin";
    const LOCAL_PASS = "azerty";

    loginForm.addEventListener('submit', (e) => {
        // Empêche le rechargement de la page
        e.preventDefault(); 
        
        // Récupération des valeurs saisies
        const usernameInput = document.getElementById('username').value;
        const passwordInput = document.getElementById('password').value;

        // Vérification immédiate
        if (usernameInput === LOCAL_USER && passwordInput === LOCAL_PASS) {
            statusDiv.innerText = "> ACCÈS AUTORISÉ. OUVERTURE DE LA SESSION...";
            statusDiv.style.color = "var(--text-color)";
            
            // Redirection immédiate vers le dashboard
            window.location.href = "index.html";
        } else {
            // Rejet immédiat
            statusDiv.innerText = "> ERREUR : IDENTIFIANTS COMPROMIS OU INVALIDES.";
            statusDiv.style.color = "red"; // Alerte visuelle
            
            // Vide uniquement le champ mot de passe pour forcer une nouvelle saisie
            document.getElementById('password').value = "";
            document.getElementById('password').focus();
        }
    });
    
});
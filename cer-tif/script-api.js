document.addEventListener('DOMContentLoaded', () => {
    console.log("Liaison API Cert.tif activée et autonome !");

    const fileInput = document.getElementById('file-upload');
    const dropZone = document.querySelector('.image-preview');
    const btnExecute = document.querySelector('.console-footer span:first-child');
    const btnExport = document.querySelector('.console-tags .tag');

    let currentDownloadUrl = "";

    // Empêcher le formulaire watermark de recharger la page
    const wmForm = document.getElementById('form-watermark-data');
    if (wmForm) {
        wmForm.addEventListener('submit', (e) => e.preventDefault());
    }

    if (btnExecute) {
        btnExecute.style.cursor = 'pointer';

        btnExecute.addEventListener('click', () => {
            if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
                alert("Veuillez d'abord importer une image.");
                return;
            }

            const activeTab = document.querySelector('.tab.active');
            const tabName = activeTab ? activeTab.innerText.trim() : "Certif complète";

            const actionMapping = {
                "Certif complète": "pipeline",
                "Watermark": "visible",
                "EXIF": "exif",
                "Stegano": "stegano"
            };
            const apiAction = actionMapping[tabName] || "pipeline";

            const formData = new FormData();
            formData.append('action', apiAction);
            formData.append('file', fileInput.files[0]);

            formData.append('wm_text', document.getElementById('watermark-msg').value || "© Cert-Art.fr");
            formData.append('wm_size', document.getElementById('watermark-taillep').value || "35");
            formData.append('wm_color', document.getElementById('watermark-couleur').value || "128,128,128");
            formData.append('wm_opacity', document.getElementById('watermark-opacite').value || "0.2");
            formData.append('wm_angle', document.getElementById('watermark-angle').value || "-30");
            formData.append('wm_spacing', document.getElementById('watermark-espace').value || "200");

            // CHANGEMENT : on appelle /api sur le MÊME serveur (plus de http://localhost:8000)
            fetch('/api', {
                method: 'POST',
                body: formData
            })
            .then(response => response.text())
            .then(rawText => {
                try {
                    const data = JSON.parse(rawText);

                    if (data.status === "success") {
                        const imageSource = data.image_base64 || data.download_url;

                        if (imageSource) {
                            currentDownloadUrl = imageSource;
                            if (dropZone) {
                                const cacheBuster = imageSource.startsWith('data:') ? '' : `?t=${new Date().getTime()}`;
                                dropZone.innerHTML = `
                                    <img src="${imageSource}${cacheBuster}"
                                         style="width: 100%; height: 100%; object-fit: cover; border: 2px solid #ff9f00;">
                                `;
                            }
                        }
                        alert(`Traitement [ ${apiAction} ] terminé avec succès !`);
                    } else {
                        alert(`Erreur du moteur : ${data.message}`);
                    }
                } catch (jsonError) {
                    document.body.style.cursor = 'default';
                    console.error("Réponse brute du serveur :", rawText);
                    alert("Le script a renvoyé une erreur système. Ouvre la console (F12) pour lire le message.");
                }
            })
            .catch(error => {
                console.error("Erreur réseau réelle :", error);
                alert("Impossible de joindre le serveur. Vérifie ton terminal.");
            });
        });
    }

    if (btnExport) {
        btnExport.style.cursor = 'pointer';
        btnExport.addEventListener('click', (e) => {
            e.preventDefault();
            if (!currentDownloadUrl) {
                alert("Aucune image n'a encore été traitée.");
                return;
            }
            const link = document.createElement('a');
            link.href = currentDownloadUrl;
            link.download = currentDownloadUrl.startsWith('data:') ? 'image_protegee.png' : currentDownloadUrl.split('/').pop();
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }
});
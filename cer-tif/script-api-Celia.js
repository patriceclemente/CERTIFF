document.addEventListener('DOMContentLoaded', () => {
    console.log("Liaison API Cert.tif activée, autonome et boostée ! 🚀");

    // =========================================================================
    // BLOCK A : GESTION DU CLIC SUR CERTIFICATION / VÉRIFICATION (ONGLETS PRINCIPAUX)
    // =========================================================================
    const navItems = document.querySelectorAll('.nav-item');
    const panelCertif = document.getElementById('panel-certification');
    const panelVerif = document.getElementById('panel-verification');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            const text = item.innerText.trim();
            if (text === "Certification") {
                panelCertif.style.display = 'block';
                panelVerif.style.display = 'none';
            } else if (text === "Vérification") {
                panelCertif.style.display = 'none';
                panelVerif.style.display = 'block';
            }
        });
    });

    // =========================================================================
    // BLOCK B : EFFET MIROIR RÉTRO POUR LES INPUTS TERMINAL
    // =========================================================================
    const inputs = document.querySelectorAll('.hidden-terminal-input');
    inputs.forEach(input => {
        const container = input.closest('.mirror-container');
        if (container) {
            const mirror = container.querySelector('.terminal-mirror');
            input.addEventListener('input', () => {
                mirror.textContent = input.value;
            });
        }
    });

    // =========================================================================
    // DÉCLARATION DES VARIABLES & ÉLÉMENTS DE CERTIFICATION
    // =========================================================================
    const fileInput = document.getElementById('file-upload');
    const dropZone = document.querySelector('.image-preview');
    const btnExecute = document.querySelector('.console-footer span:first-child');
    const btnExport = document.querySelector('.console-tags .tag');
    const btnNext = document.getElementById('btn-next');
    const tabs = document.querySelectorAll('.tab');
    
    let currentCertifStep = 0; // 0: Watermark, 1: EXIF, 2: Stegano, 3: Signature, 4: Blockchain
    let currentDownloadUrl = ""; // Stockera l'image finale pour l'export

    // Réinitialiser le parcours si l'utilisateur change d'image
    const btnImport = document.getElementById('btn-import');
    if (btnImport) btnImport.addEventListener('click', () => fileInput.click());
    if (dropZone) dropZone.addEventListener('click', () => fileInput.click());
    
    if (fileInput) {
        fileInput.addEventListener('change', () => {
            currentCertifStep = 0;
            console.log("🔄 Nouvelle image détectée. Stepper réinitialisé à l'étape 0.");
        });
    }

    // Sécurité anti-rechargement du formulaire de réglages
    const wmForm = document.getElementById('form-watermark-data');
    if (wmForm) wmForm.addEventListener('submit', (e) => e.preventDefault());

    // =========================================================================
    // FONCTION CENTRALISÉE D'ENVOI À FLASK (NON-BLOQUANTE VISUELLEMENT)
    // =========================================================================
    function executerEtapePipeline(apiAction, nomEtapeAffichage, isNextClick = false) {
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            alert("Veuillez d'abord importer une image via la zone [ + ].");
            return;
        }

        const formData = new FormData();
        formData.append('action', apiAction);
        formData.append('file', fileInput.files[0]);

        // Récupération dynamique des réglages curseurs de l'IHM
        formData.append('wm_text', document.getElementById('watermark-msg')?.value || "© Cert-Art.fr");
        formData.append('wm_size', document.getElementById('watermark-taillep')?.value || "35");
        formData.append('wm_color', document.getElementById('watermark-couleur')?.value || "128,128,128");
        formData.append('wm_opacity', document.getElementById('watermark-opacite')?.value || "0.2");
        formData.append('wm_angle', document.getElementById('watermark-angle')?.value || "-45");
        formData.append('wm_spacing', document.getElementById('watermark-espace')?.value || "300");
        formData.append('stegano_message', document.getElementById('stegano-msg')?.value || "defaut");

        // ⚡ RETOUR VISUEL IMMÉDIAT
        if (btnExecute) btnExecute.innerText = "[⏳] Calcul...";
        if (btnNext) btnNext.innerText = "[⏳] Calcul...";

        console.log(`📡 [Étape ${currentCertifStep + 1}] Envoi de l'action : ${apiAction}`);

        fetch('/api', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                if (data.image_base64) {
                    currentDownloadUrl = data.image_base64;
                    if (dropZone) {
                        dropZone.innerHTML = `<img src="${data.image_base64}" style="width: 100%; height: 100%; object-fit: cover; border: 2px solid #ff9f00;">`;
                    }
                }
                
                // On passe officiellement à l'étape suivante si c'est le bouton Next
                if (isNextClick) {
                    currentCertifStep++;
                }
                alert(`Succès : ${nomEtapeAffichage} validé ! Étape suivante prête.`);
            } else {
                alert(`Erreur au cours de l'étape : ${data.message}`);
            }

            // 🔓 On rétablit les textes d'origine
            if (btnNext) btnNext.innerText = "[N] Next ➔";
            if (btnExecute) btnExecute.innerText = "[↵] Exécuter";
        })
        .catch(error => {
            console.error("Erreur réseau :", error);
            alert("Erreur de communication avec le serveur Flask.");
            if (btnNext) btnNext.innerText = "[N] Next ➔";
            if (btnExecute) btnExecute.innerText = "[↵] Exécuter";
        });
    }

    // =========================================================================
    // GESTION DU SCRIPT DE NAVIGATION INTERNE DES ONGLETS CONSOLE
    // =========================================================================
    function basculerVisualisationOnglet(nomOnglet, idConsole) {
        tabs.forEach(tab => tab.classList.toggle('active', tab.innerText.trim() === nomOnglet));
        const consoles = ['console-watermark', 'console-exif', 'console-stegano', 'console-sign', 'console-block'];
        consoles.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = (id === idConsole) ? 'block' : 'none';
        });
    }

    // =========================================================================
    // GESTION DU BOUTON NEXT ➔ (PIPELINE SÉQUENTIEL)
    // =========================================================================
    if (btnNext) {
        btnNext.addEventListener('click', (e) => {
            e.preventDefault();
            
            if (currentCertifStep === 0) {
                basculerVisualisationOnglet("Watermark", "console-watermark");
                executerEtapePipeline("visible", "Étape 1/5 : Filigrane Visible", true);
            } else if (currentCertifStep === 1) {
                basculerVisualisationOnglet("EXIF", "console-exif");
                executerEtapePipeline("exif", "Étape 2/5 : Métadonnées EXIF", true);
            } else if (currentCertifStep === 2) {
                basculerVisualisationOnglet("Stegano", "console-stegano");
                executerEtapePipeline("stegano", "Étape 3/5 : Filigrane Invisible (Stéganographie)", true);
            } else if (currentCertifStep === 3) {
                basculerVisualisationOnglet("Signature Num.", "console-sign");
                executerEtapePipeline("signature", "Étape 4/5 : Signature Numérique", true);
            } else if (currentCertifStep === 4) {
                basculerVisualisationOnglet("Blockchain OTS", "console-block");
                executerEtapePipeline("blockchain", "Étape 5/5 : Horodatage Blockchain OTS", true);
            } else {
                alert("🎉 Certification 100% complète ! Vous pouvez exporter l'image définitive.");
            }
        });
    }

    // =========================================================================
    // BOUTON CLASSIQUE EXÉCUTER [↵] (POUR LES ACTIONS UNITAIRES)
    // =========================================================================
    if (btnExecute) {
        btnExecute.style.cursor = 'pointer';
        btnExecute.addEventListener('click', (e) => {
            e.preventDefault();
            const activeTab = document.querySelector('.tab.active');
            const tabName = activeTab ? activeTab.innerText.trim() : "Certif complète";

            if (tabName === "Certif complète") {
                alert("Pour la Certification Complète, veuillez utiliser le bouton 'Next ➔' juste à côté d'Exporter pour avancer pas à pas !");
                return;
            }

            const actionMapping = {
                "Watermark": "visible",
                "EXIF": "exif",
                "Stegano": "stegano",
                "Signature Num.": "signature",
                "Blockchain OTS": "blockchain"
            };
            
            const singleAction = actionMapping[tabName];
            if (singleAction) {
                executerEtapePipeline(singleAction, `Module individuel [${tabName}]`);
            }
        });
    }

    // =========================================================================
    // BOUTON EXPORTER [E]
    // =========================================================================
    if (btnExport) {
        btnExport.style.cursor = 'pointer';
        btnExport.addEventListener('click', (e) => {
            e.preventDefault();
            if (!currentDownloadUrl) {
                alert("Aucune image traitée disponible pour l'export.");
                return;
            }
            const link = document.createElement('a');
            link.href = currentDownloadUrl;
            link.download = 'image_certifiee_system.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // =========================================================================
    // MODULE DE VÉRIFICATION AUTOMATIQUE (PANNEAU AUDIT TECHNIQUE)
    // =========================================================================
    const fileInputVerif = document.getElementById('file-upload-verif');
    const btnImportVerif = document.getElementById('btn-import-verif');
    const dropZoneVerif = document.getElementById('drop-zone-verif');
    const resultsContainer = document.getElementById('verif-results-container');
    const statusVerifText = document.getElementById('file-status-verif');

    if (btnImportVerif) btnImportVerif.addEventListener('click', () => fileInputVerif.click());
    if (dropZoneVerif) dropZoneVerif.addEventListener('click', () => fileInputVerif.click());

    if (fileInputVerif) {
        fileInputVerif.addEventListener('change', () => {
            if (fileInputVerif.files.length === 0) return;

            const file = fileInputVerif.files[0];
            if (statusVerifText) statusVerifText.innerText = "Analyse en cours...";

            // Affichage instantané de l'aperçu de l'image à auditer
            const reader = new FileReader();
            reader.onload = (e) => {
                if (dropZoneVerif) {
                    dropZoneVerif.innerHTML = `<img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover;">`;
                }
            };
            reader.readAsDataURL(file);

            // Préparation du colis d'audit pour Flask
            const formData = new FormData();
            formData.append('action', 'report'); 
            formData.append('file', file);

            fetch('/api', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (statusVerifText) statusVerifText.innerText = "Terminée";
                
                if (data.status === "success" && data.terminal_output) {
                    // Génération dynamique de l'interface du rapport d'audit avec les couleurs de sécurité
                    resultsContainer.innerHTML = `
                        <div class="console-panel" style="border-color: #ff9f00; margin-top: 15px;">
                            <div class="console-header" style="background: #ff9f00; color: #000; padding: 4px 10px; font-weight: bold;">
                                <span>[📊 RAPPORT D'AUDIT TECHNIQUE SÉCURISÉ]</span>
                            </div>
                            <div class="console-body" style="padding: 15px; font-family: monospace; background: #000; max-height: 250px; overflow-y: auto;">
                                <ul style="list-style: none; padding: 0; margin: 0; line-height: 1.6; text-align: left;">
                                    ${data.terminal_output.map(line => {
                                        let color = "#fff"; 
                                        if (line.includes("[OK]")) color = "#00ff00"; // Vert succès
                                        if (line.includes("[ERROR]") || line.includes("[WARN]") || line.includes("[ERREUR]")) color = "#ff0000"; // Rouge alerte
                                        return `<li style="color: ${color};">${line}</li>`;
                                    }).join('')}
                                </ul>
                            </div>
                        </div>
                    `;
                } else {
                    resultsContainer.innerHTML = `<p style="color: red; font-family: monospace;">Erreur lors de l'audit : ${data.message}</p>`;
                }
            })
            .catch(err => {
                if (statusVerifText) statusVerifText.innerText = "Échec connexion";
                alert("Impossible de joindre le serveur Flask pour lancer le rapport d'audit.");
            });
        });
    }
});
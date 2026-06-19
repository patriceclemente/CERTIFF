function glitcherElement(element, intensity) {
                    if (!element) return; 
                    const mot = element.innerText.trim();
                    element.style.opacity = '0.4';
                    element.style.pointerEvents = 'none';            // non cliquable
                    setInterval(() => { element.innerText = Dinguerie(mot, intensity); }, 80);
                }

function Dinguerie(cible, intensity) {
    const n = cible.length;
    const lettres = '0123456789&@#%$%$£éàçΩωΦβΨΛζλΔδΘθηçΩωΦβΨΛαλΔδΘθηΓγ';
    // on part du mot d'origine, lettre par lettre
    const chars = cible.split('');
    const nbGlitch = Math.floor(Math.random() * intensity);
    const positions = [];
    while (positions.length < nbGlitch) {
        const p = Math.floor(Math.random() * n);
        if (!positions.includes(p)) positions.push(p);   // pas deux fois la même
    }
    // on remplace ces positions par un caractère aléatoire
    for (const p of positions) {
        chars[p] = lettres[Math.floor(Math.random() * lettres.length)];
    }
    return chars.join('');
}

function griser(btn) {
    if (!btn) return;
    btn.style.opacity = '0.4';
    btn.style.pointerEvents = 'none';
}

function chargerHistorique() {
    const container = document.getElementById('historique-container');
    container.innerHTML = '> Chargement...';

    fetch('/api/historique')
        .then(r => r.json())
        .then(data => {
            if (!data.ok) {
                container.innerHTML = '> Connecte-toi pour voir ton historique.';
                return;
            }
            if (data.depots.length === 0) {
                container.innerHTML = '> Aucun dépôt pour le moment.';
                return;
            }

            container.innerHTML = '';

            data.depots.forEach(depot => {
                const tile = document.createElement('div');
                tile.className = 'histo-tile';

                // ATTENTION: Il faudra que API Python renvoie un lien vers l'image 
                // Ex: depot.url_image (base64 ou lien /static/uploads/...)
                // Si l'URL n'est pas encore gérée côté Python, ça affichera une image vide.
                const imgSrc = depot.url_image || '';

                tile.innerHTML = `
                    <img src="${imgSrc}" alt="aperçu">
                    <span>${depot.nom_fichier}</span>
                `;

                // Clic sur l'image = ouverture de la modale
                tile.addEventListener('click', () => {
                    afficherDetailsHisto(depot, imgSrc);
                });

                container.appendChild(tile);
            });
        })
        .catch(err => {
            container.innerHTML = '> Erreur de chargement.';
            console.error('Erreur historique :', err);
        });
}

// --- Nouvelle fonction pour gérer la fenêtre modale ---
function afficherDetailsHisto(depot, imgSrc) {
    const modal = document.getElementById('histo-modal');
    const modalFilename = document.getElementById('modal-filename');
    const modalImg = document.getElementById('modal-img');
    const modalDetails = document.getElementById('modal-details');
    if (!modal) return;

    const tailleKo = (depot.taille / 1024).toFixed(1);
    modalFilename.innerText = `// ${depot.nom_fichier}`;
    modalImg.src = imgSrc;

    // Injecte les détails avec l'esthétique "default settings"
    modalDetails.innerHTML = `
        <p>// Détails d'intégrité :</p>
        <ul style="list-style: none; padding-left: 0;">
            <li style="margin-bottom: 8px;">> <strong>Date :</strong> ${depot.date_depot}</li>
            <li style="margin-bottom: 8px;">> <strong>Taille :</strong> ${tailleKo} Ko</li>
            <li style="margin-bottom: 8px; word-break: break-all;">> <strong>Hash :</strong> ${depot.hash_fichier}</li>
        </ul>
        <div class="console-tags" style="margin-top: 30px;">
            <button class="tag" style="width: 100%;">[↓] Télécharger le fichier source</button>
        </div>
    `;

    // Affiche le pop-up
    modal.style.display = 'flex';

    // Bouton pour fermer
    document.getElementById('modal-close').onclick = () => { modal.style.display = 'none'; };
}

document.addEventListener('DOMContentLoaded', () => {

    // Déconnexion 
    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) {
        btnLogout.style.cursor = 'pointer';
        btnLogout.addEventListener('click', () => {
            fetch('/api/deconnexion', { method: 'POST' })
                .then(r => r.json())
                .then(data => { if (data.ok) window.location.href = '/index.html'; })
                .catch(err => console.error('Erreur déconnexion :', err));
        });
    }

    // Connexion : renvoyer vers la page de login 
    const btnLoginIcon = document.getElementById('btn-login');
    if (btnLoginIcon) {
        btnLoginIcon.style.cursor = 'pointer';
        btnLoginIcon.addEventListener('click', () => { window.location.href = '/'; });
    }

    // Gestion de la navigation latérale
    const navItems = document.querySelectorAll('.nav-item');
    const panelCertif = document.getElementById('panel-certification');
    const panelVerif = document.getElementById('panel-verification');
    const panelHisto = document.getElementById('panel-historique');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();

            // Retire la classe 'active' de tous les éléments
            navItems.forEach(nav => nav.classList.remove('active'));

            // Ajoute la classe 'active' à l'élément cliqué
            item.classList.add('active');
            const cible = item.innerText.trim();

            if (panelCertif) panelCertif.style.display = (cible === "Certification") ? "block" : "none";
            if (panelVerif)  panelVerif.style.display  = (cible === "Vérification") ? "block" : "none";
            if (panelHisto)  panelHisto.style.display  = (cible === "Historique") ? "block" : "none";

            if (cible === "Historique") chargerHistorique();
        });
    });

    const dropZone = document.querySelector('.image-preview');
    const fileInput = document.getElementById('file-upload');
    const fileStatus = document.querySelector('.details h3 .highlight');
    const btnImport = document.getElementById('btn-import');

    // Variable globale pour stocker tous les fichiers du lot + état de connexion
    let selectedFiles = [];
    let estConnecte = false;
    window.currentDepotId = null;

    function afficherApercu(files, zone) {
        if (!zone || !files.length) return;
        const reader = new FileReader();
        reader.onload = function (e) {
            let html = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;">`;
            if (files.length > 1) {
                html += `<div style="position:absolute;bottom:5px;right:5px;background:var(--text-color);color:var(--bg-color);padding:2px 6px;font-weight:bold;border:1px solid var(--bg-color);">+${files.length - 1}</div>`;
            }
            zone.style.position = "relative";
            zone.innerHTML = html;
            zone.style.border = "none";
        };
        // On lit uniquement le premier fichier pour la miniature
        reader.readAsDataURL(files[0]);
    }

    //enregistrer chaque fichier déposé en base ---
    function enregistrerDepots(files) {
        files.forEach(file => {
            const formData = new FormData();
            formData.append('file', file);
            fetch('/api/upload', { method: 'POST', body: formData })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'success') {
                        
                        if (data.depot_id) {
                            window.currentDepotId = data.depot_id;
                            console.log(`Dépôt enregistré : ${file.name} (id=${data.depot_id})`);
                            if (fileStatus) fileStatus.innerText = `${file.name} (sauvegardé)`;
                        } else {
                            console.warn(`${file.name} non sauvegardé (invité non connecté).`);
                        }
                    } else {
                        console.error(`Erreur dépôt ${file.name} :`, data.message);
                        if (fileStatus) fileStatus.innerText = `ERREUR: ${data.message}`;
                    }
                })
                .catch(err => console.error(`Erreur réseau ${file.name} :`, err));
        });
    }

    // [Soumettre] : enregistre le dépôt en base, uniquement si connecté.
    // N'ouvre PLUS l'explorateur (le dépôt se fait par la zone [ + ] ou le drag&drop).
    if (btnImport) {
        btnImport.addEventListener('click', () => {
            if (!estConnecte) return;                 // invité : pas de sauvegarde
            if (selectedFiles.length === 0) {
                if (fileStatus) fileStatus.innerText = "Dépose d'abord une image.";
                return;
            }
            enregistrerDepots(selectedFiles);
        });
    }

    // Clic sur la zone -> ouvre l'explorateur (dépôt + aperçu)
    if (dropZone) {
        dropZone.addEventListener('click', () => fileInput.click());
    }

    // --- Gestion du choix des fichiers --- (aperçu seulement)
    if (fileInput) {
        fileInput.addEventListener('change', function () {
            if (!this.files || this.files.length === 0) return;
            selectedFiles = Array.from(this.files);

            if (fileStatus) {
                fileStatus.innerText = selectedFiles.length === 1
                    ? selectedFiles[0].name
                    : `[${selectedFiles.length} FICHIERS ]`;
            }

            afficherApercu(selectedFiles, dropZone);
        });
    }

    //drag and drop
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.backgroundColor = 'var(--text-color)';
            dropZone.style.color = 'var(--bg-color)';
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.style.backgroundColor = '';
            dropZone.style.color = '';
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.backgroundColor = '';
            dropZone.style.color = '';
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                fileInput.dispatchEvent(new Event('change')); // Déclenche le code au-dessus
            }
        });
    }

    // --- Gestion du bouton Annuler ---
    const btnCancel = document.getElementById('btn-cancel');
    if (btnCancel) {
        btnCancel.addEventListener('click', () => {
            // On vide notre tableau
            selectedFiles = [];

            // On réinitialise l'interface
            dropZone.innerHTML = `<div class="placeholder-art"><br><p id="depot_certif">[ + ]</p><br></div>`;
            dropZone.style.border = "";
            if (fileStatus) fileStatus.innerText = "en attente...";
            fileInput.value = "";
        });
    }

    // affichage username
    fetch('/api/me')
        .then(response => response.json())
        .then(data => {
            
            const usernameDiv = document.getElementById('username');
            if (data.ok) {
                usernameDiv.innerText = data.username;
                estConnecte = true;
                griser(btnLoginIcon);
            } else {
                estConnecte = false;
                griser(btnLogout);
                glitcherElement(btnImport,2); 
                glitcherElement(btnImportVerif, 2);
                setInterval(() => {
                    usernameDiv.innerText = Dinguerie('NOT_FOUND', 4);
                }, 60);   // rythme (ms)
                // INVITÉ : masquer l'onglet Vérification et Historique (sidebar) 
                //a securisé quand on connectera l'api avec les fonctionnalités bloquées
                
                // --- onglets sidebar bloqués ---
                document.querySelectorAll('.nav-item').forEach(item => {
                    if (item.innerText.trim() === 'Historique') glitcherElement(item, 4);
                });

                // --- onglet Blockchain OTS bloqué ---
                document.querySelectorAll('.tab').forEach(tab => {
                    if (tab.innerText.trim() === 'Blockchain OTS') glitcherElement(tab, 4);
                });
            }
        })
        .catch(err => console.error('Impossible de récupérer l\'utilisateur :', err));

    //gestion des onglets 
    const tabs = document.querySelectorAll('.tab');
    const consoleHeaderTitle = document.querySelector('.console-header span:first-child');
    const consoleHeader = document.querySelector('.console-header');
    const consoleFooter = document.querySelector('.console-footer');
    const actionButtons = document.getElementById('action-buttons');
    const btnExport = document.querySelector('.console-tags .tag');
    const btnNextBlock = document.getElementById('btn-next');

    //dico
    const tabExplanations = {
        "": "[CHOISIR UN MODE CERTIFICATION] : Vous pouvez effectuer les certifications séparémment et exporter dès que besoin.",
        "Watermark": "[MODE : WARTERMARK] Incrustation d'un filigrane visible.",
        "EXIF": "[MODE : EXIF] Injection de métadonnées d'identification.",
        "Stegano": "[MODE : STEGANO] Insertion de métadonnées invisibles.",
        "Signature Num.": "[MODE : SIGNATURE] Chiffrement asymétrique pour authentification d'identité.",
        "Blockchain OTS": "[MODE : BLOCKCHAIN] Horodatage et preuve."
    };

    const tabConsoleMap = {
        "Watermark":      { console: "console-watermark", focus: "watermark-msg" },
        "EXIF":           { console: "console-exif",      focus: "exif-auteur" },
        "Stegano":        { console: "console-stegano",   focus: "stegano-msg" },
        "Signature Num.": { console: "console-sign",      focus: "sign-mdp" },
        "Blockchain OTS": { console: "console-block",     focus: null }
    };
    const allConsoles = ["console-watermark", "console-exif", "console-stegano", "console-sign", "console-block"];

    if (consoleHeaderTitle) {
        consoleHeaderTitle.innerText = tabExplanations[""];

        // --- MASQUER LES LIGNES ET LE BOUTON EXÉCUTER AU CHARGEMENT ---
        if (consoleHeader) consoleHeader.style.borderBottom = "none";
        if (consoleFooter) consoleFooter.style.display = "none";
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const tabName = tab.innerText.trim();

            if (tabExplanations[tabName] && consoleHeaderTitle) {
                consoleHeaderTitle.innerText = tabExplanations[tabName];
            }

            const mapping = tabConsoleMap[tabName];
            allConsoles.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.style.display = (mapping && id === mapping.console) ? "block" : "none";
            });
            if (mapping && mapping.focus) {
                const f = document.getElementById(mapping.focus);
                if (f) f.focus();
            }

            if (actionButtons) actionButtons.style.display = 'flex';

            // --- RÉAFFICHER LES LIGNES ET LE BOUTON EXÉCUTER ---
            if (consoleHeader) consoleHeader.style.borderBottom = "1px dashed var(--border-color)";
            if (consoleFooter) consoleFooter.style.display = "flex";

            if (tabName === "Blockchain OTS") {
                if (btnExport) btnExport.innerText = "[+] Envoyer vers la Blockchain";
                if (btnNextBlock) btnNextBlock.style.display = "none";
            } else {
                if (btnExport) btnExport.innerText = "[E] Exporter";
                if (btnNextBlock) btnNextBlock.style.display = "inline-block";
            }
        });
    });

    // --- L'effet miroir pour TOUS les curseurs du terminal ---
    document.querySelectorAll('.hidden-terminal-input').forEach(input => {
        // On cherche automatiquement le miroir qui correspond à l'ID de l'input
        const mirror = document.getElementById(input.id + '-mirror');

        if (mirror) {
            // Recopie instantanément le texte tapé
            input.addEventListener('input', (e) => { mirror.textContent = e.target.value; });
        }
    });

    // --- GESTION DES THÈMES ---
    const btnSettings = document.getElementById('btn-settings');
    const themeMenu = document.getElementById('theme-menu');
    const themeBtns = document.querySelectorAll('.theme-btn');

    if (btnSettings && themeMenu) {
        // 1. Ouvrir/Fermer le menu au clic sur l'engrenage
        btnSettings.addEventListener('click', (e) => {
            e.stopPropagation(); // Évite la fermeture immédiate
            themeMenu.style.display = themeMenu.style.display === 'none' ? 'flex' : 'none';
        });

        // 2. Fermer le menu si on clique n'importe où ailleurs sur la page
        document.addEventListener('click', () => { themeMenu.style.display = 'none'; });

        // 3. Empêcher la fermeture si on clique à l'intérieur du menu
        themeMenu.addEventListener('click', (e) => e.stopPropagation());

        // 4. Appliquer le thème choisi
        themeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Nettoyer les anciens thèmes
                document.body.classList.remove('theme-blue', 'theme-beige', 'theme-grey');

                // Ajouter le nouveau (sauf si on retourne au défaut)
                const selectedTheme = btn.getAttribute('data-theme');
                if (selectedTheme !== 'theme-default') document.body.classList.add(selectedTheme);

                // --- AJOUT : METTRE À JOUR LE FAVICON ---
                const favicon = document.getElementById('dynamic-favicon');
                if (favicon) {
                    if (selectedTheme === 'theme-default') favicon.href = 'icons/icon-amber.png';
                    if (selectedTheme === 'theme-blue')    favicon.href = 'icons/icon-blue.png';
                    if (selectedTheme === 'theme-beige')   favicon.href = 'icons/icon-beige.png';
                    if (selectedTheme === 'theme-grey')    favicon.href = 'icons/icon-grey.png';
                }

                // Fermer le menu
                themeMenu.style.display = 'none';
            });
        });
    }

    // --- 3. LOGIQUE D'UPLOAD : ZONE VÉRIFICATION ---
    const dropZoneVerif = document.getElementById('drop-zone-verif');
    const fileInputVerif = document.getElementById('file-upload-verif');
    const fileStatusVerif = document.getElementById('file-status-verif');
    const btnImportVerif = document.getElementById('btn-import-verif');
    const btnCancelVerif = document.getElementById('btn-cancel-verif');

    if (btnImportVerif) btnImportVerif.addEventListener('click', () => fileInputVerif.click());
    if (dropZoneVerif)  dropZoneVerif.addEventListener('click', () => fileInputVerif.click());

    if (fileInputVerif) {
        fileInputVerif.addEventListener('change', function () {
            if (!this.files || this.files.length === 0) return;
            const files = Array.from(this.files);
            if (fileStatusVerif) {
                fileStatusVerif.innerText = files.length === 1 ? files[0].name : `[${files.length} FICHIERS ]`;
            }
            afficherApercu(files, dropZoneVerif);
        });
    }

    if (dropZoneVerif) {
        dropZoneVerif.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZoneVerif.style.backgroundColor = 'var(--text-color)';
            dropZoneVerif.style.color = 'var(--bg-color)';
        });
        dropZoneVerif.addEventListener('dragleave', () => {
            dropZoneVerif.style.backgroundColor = '';
            dropZoneVerif.style.color = '';
        });
        dropZoneVerif.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZoneVerif.style.backgroundColor = '';
            dropZoneVerif.style.color = '';
            if (e.dataTransfer.files.length) {
                fileInputVerif.files = e.dataTransfer.files;
                fileInputVerif.dispatchEvent(new Event('change'));
            }
        });
    }

    if (btnCancelVerif) {
        btnCancelVerif.addEventListener('click', () => {
            dropZoneVerif.innerHTML = `<div class="placeholder-art"><br><p id="depot_verif">[ ? ]</p><br></div>`;
            dropZoneVerif.style.border = "";
            if (fileStatusVerif) fileStatusVerif.innerText = "en attente...";
            fileInputVerif.value = "";
            const verifContainer = document.getElementById('verif-results-container');
            if (verifContainer) verifContainer.innerHTML = '';
        });
    }
});
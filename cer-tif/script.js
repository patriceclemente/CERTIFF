function Dinguerie(cible, intensity) {
    // Implementation for Dinguerie function
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

/*function chargerHistorique() {
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
                // taille en Ko, arrondie
                const tailleKo = (depot.taille / 1024).toFixed(1);

                const ligne = document.createElement('div');
                ligne.className = 'console-panel';
                ligne.style.marginBottom = '10px';
                ligne.innerHTML = `
                    <div class="console-header">
                        <span>// ${depot.nom_fichier}</span>
                        <span>${depot.date_depot}</span>
                    </div>
                    <div style="padding-top:8px; opacity:0.8;">
                        > Taille : ${tailleKo} Ko<br>
                        > Hash : ${depot.hash_fichier.substring(0, 16)}...
                    </div>
                `;
                container.appendChild(ligne);
            });
        })
        .catch(err => {
            container.innerHTML = '> Erreur de chargement.';
            console.error('Erreur historique :', err);
        });
}
*/

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
    document.getElementById('modal-close').onclick = () => {
        modal.style.display = 'none';
    };
}

document.addEventListener('DOMContentLoaded', () => {
    
    // Déconnexion 
    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) {
        btnLogout.style.cursor = 'pointer';
        btnLogout.addEventListener('click', () => {
            fetch('/api/deconnexion', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.ok) {
                        window.location.href = '/index.html';   // retour à la page de login
                    }
                })
                .catch(err => console.error('Erreur déconnexion :', err));
        });
    }

    // Connexion : renvoyer vers la page de login 
    const btnLoginIcon = document.getElementById('btn-login');
    if (btnLoginIcon) {
        btnLoginIcon.style.cursor = 'pointer';
        btnLoginIcon.addEventListener('click', () => {
            window.location.href = '/';   // la racine sert login.html
        });
    }
    
    // Gestion de la navigation latérale
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Retire la classe 'active' de tous les éléments
            navItems.forEach(nav => nav.classList.remove('active'));
            
            // Ajoute la classe 'active' à l'élément cliqué
            e.target.classList.add('active');

            const panelCertif = document.getElementById('panel-certification');
            const panelVerif = document.getElementById('panel-verification');
            const panelHisto = document.getElementById('panel-historique');
            const targetMenu = e.target.innerText.trim();

            if (targetMenu === "Vérification") {
                if(panelCertif) panelCertif.style.display = "none";
                if(panelVerif) panelVerif.style.display = "block";
                if(panelHisto) panelHisto.style.display = "none";
            } else if (targetMenu === "Certification") {
                if(panelVerif) panelVerif.style.display = "none";
                if(panelCertif) panelCertif.style.display = "block";
                if(panelHisto) panelHisto.style.display = "none";
            } else if (targetMenu === "Historique") {
                if(panelCertif) panelCertif.style.display = "none";
                if(panelVerif) panelVerif.style.display = "none";
                if(panelHisto) panelHisto.style.display = "block";
                chargerHistorique();
            }
        });
    });

    const dropZone = document.querySelector('.image-preview');
    const fileInput = document.getElementById('file-upload');
    const fileStatus = document.querySelector('.details h3 .highlight');
    const btnImport = document.getElementById('btn-import');

    dropZone.addEventListener('click', () => fileInput.click());
    if(btnImport){
        btnImport.addEventListener('click', () => fileInput.click());
    }

    // affichage username
    
    fetch('/api/me')
    .then(response => response.json())
    .then(data => {
        const usernameDiv = document.getElementById('username');
        if (data.ok) {
            usernameDiv.innerText = data.username;
            griser(btnLoginIcon)
        } else {
            griser(btnLogout)
            setInterval(() => {
            usernameDiv.innerText = Dinguerie('NOT_FOUND', 4);
            }, 60);   // rythme (ms)
           // INVITÉ : masquer l'onglet Vérification et Historique (sidebar) 
           //a securisé quand on connectera l'api avec les fonctionnalités bloquées
           function glitcherElement(element,intensity) {
                const mot = element.innerText.trim();   // on mémorise le vrai mot
                element.style.opacity = '0.4';
                element.style.pointerEvents = 'none';            // non cliquable
                setInterval(() => {
                    element.innerText = Dinguerie(mot, intensity);
                }, 80);
            }
            // --- onglets sidebar bloqués ---
            document.querySelectorAll('.nav-item').forEach(item => {
                const txt = item.innerText.trim();
                if (txt === 'Vérification' || txt === 'Historique') {
                    glitcherElement(item, 4);
                }
            });

            // --- onglet Blockchain OTS bloqué ---
            document.querySelectorAll('.tab').forEach(tab => {
                if (tab.innerText.trim() === 'Blockchain OTS') {
                    glitcherElement(tab, 4);
                }
            });
        }
    })
    .catch(err => {
        console.error('Impossible de récupérer l\'utilisateur :', err);
    });

    // Variable globale pour stocker tous les fichiers du lot
    let selectedFiles = [];

    // --- Gestion du choix des fichiers ---
    fileInput.addEventListener('change', function(){
        if (this.files && this.files.length > 0) {
            // On convertit les fichiers en tableau pour faciliter l'envoi futur au Python
            selectedFiles = Array.from(this.files);
            
            // Mise à jour du texte à droite
            if (selectedFiles.length === 1) {
                fileStatus.innerText = selectedFiles[0].name;
            } else {
                fileStatus.innerText = `[${selectedFiles.length} FICHIERS ]`;
            }
            
            // Affichage de la miniature du premier fichier
            const reader = new FileReader();
            reader.onload = function(e) {
                // Création de l'image
                let htmlContent = `<img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover;">`;
                
                // Si plusieurs fichiers, on ajoute un badge rétro par-dessus
                if (selectedFiles.length > 1) {
                    const extraCount = selectedFiles.length - 1;
                    htmlContent += `
                        <div style="position: absolute; bottom: 5px; right: 5px; background: var(--text-color); color: var(--bg-color); padding: 2px 6px; font-weight: bold; border: 1px solid var(--bg-color);">
                            +${extraCount}
                        </div>
                    `;
                }
                
                dropZone.style.position = "relative"; // Nécessaire pour le badge absolu
                dropZone.innerHTML = htmlContent;
                dropZone.style.border = "none";
            }
            // On lit uniquement le premier fichier pour la miniature
            reader.readAsDataURL(selectedFiles[0]);
            //enregistrer chaque fichier déposé en base ---
            selectedFiles.forEach(file => {
                const formData = new FormData();
                formData.append('file', file);

                fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'success') {
                        console.log(`Dépôt enregistré : ${file.name} (id=${data.depot_id})`);
                    } else {
                        console.error(`Erreur dépôt ${file.name} :`, data.message);
                    }
                })
                .catch(err => console.error(`Erreur réseau dépôt ${file.name} :`, err));
            });
        }
    });

    //drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.backgroundColor = 'var(--text-color)';
        dropZone.style.color = 'var(--bg-color)';
    })

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

    // --- Gestion du bouton Annuler ---
    const btnCancel = document.getElementById('btn-cancel');

    if(btnCancel){
        btnCancel.addEventListener('click', () =>{
            // On vide notre tableau
            selectedFiles = [];
            
            // On réinitialise l'interface
            dropZone.innerHTML = `
                <div class="placeholder-art">
                    <br>
                    <p id="depot">[ + ]</p><br>
                </div>
            `;
            dropZone.style.border = "";
            fileStatus.innerText = "en attente...";
            fileInput.value = "";
        });
    }

    //gestion des onglets 
    const tabs = document.querySelectorAll('.tab');
    const consoleHeaderTitle = document.querySelector('.console-header span:first-child');

    //dico
    const tabExplanations = {
        "" : "[CHOISIR UN MODE CERTIFICATION] : Vous pouvez effectuer les certifications séparémment et exporter dès que besoin.",
        "Watermark" : "[MODE : WARTERMARK] Incrustation d'un filigrane visible.",
        "EXIF" : "[MODE : EXIF] Injection de métadonnées d'identification.",
        "Stegano" : "[MODE : STEGANO] Insertion de métadonnées invisibles.",
        "Signature Num." : "[MODE : SIGNATURE] Chiffrement asymétrique pour authentification d'identité.",
        "Blockchain OTS" : "[MODE : BLOCKCHAIN] Horodatage et preuve."
    }

    if(consoleHeaderTitle){
        consoleHeaderTitle.innerText = tabExplanations[""];
        
        // --- MASQUER LES LIGNES ET LE BOUTON EXÉCUTER AU CHARGEMENT ---
        const consoleHeader = document.querySelector('.console-header');
        const consoleFooter = document.querySelector('.console-footer');
        if (consoleHeader) consoleHeader.style.borderBottom = "none";
        if (consoleFooter) consoleFooter.style.display = "none";
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');

            const tabName = e.target.innerText.trim();
            if (tabExplanations[tabName]){
                consoleHeaderTitle.innerText = tabExplanations[tabName];
            }

            const actionButtons = document.getElementById('action-buttons');
            if (actionButtons) actionButtons.style.display = 'flex';

            // --- RÉAFFICHER LES LIGNES ET LE BOUTON EXÉCUTER ---
            const consoleHeader = document.querySelector('.console-header');
            const consoleFooter = document.querySelector('.console-footer');
            if (consoleHeader) consoleHeader.style.borderBottom = "1px dashed var(--border-color)";
            if (consoleFooter) consoleFooter.style.display = "flex";
        })
    })

    // --- 3. LOGIQUE D'UPLOAD : ZONE VÉRIFICATION ---
    const dropZoneVerif = document.getElementById('drop-zone-verif');
    const fileInputVerif = document.getElementById('file-upload-verif');
    const fileStatusVerif = document.getElementById('file-status-verif');
    const btnImportVerif = document.getElementById('btn-import-verif');
    const btnCancelVerif = document.getElementById('btn-cancel-verif');
    let selectedFilesVerif = [];

    dropZoneVerif.addEventListener('click', () => fileInputVerif.click());
    if(btnImportVerif) btnImportVerif.addEventListener('click', () => fileInputVerif.click());

    fileInputVerif.addEventListener('change', function(){
        if (this.files && this.files.length > 0) {
            selectedFilesVerif = Array.from(this.files);
            fileStatusVerif.innerText = selectedFilesVerif.length === 1 ? selectedFilesVerif[0].name : `[${selectedFilesVerif.length} FICHIERS ]`;
            
            const reader = new FileReader();
            reader.onload = function(e) {
                let htmlContent = `<img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover;">`;
                if (selectedFilesVerif.length > 1) {
                    htmlContent += `<div style="position: absolute; bottom: 5px; right: 5px; background: var(--text-color); color: var(--bg-color); padding: 2px 6px; font-weight: bold; border: 1px solid var(--bg-color);">+${selectedFilesVerif.length - 1}</div>`;
                }
                dropZoneVerif.style.position = "relative";
                dropZoneVerif.innerHTML = htmlContent;
                dropZoneVerif.style.border = "none";
            }
            reader.readAsDataURL(selectedFilesVerif[0]);
        }
    });

    dropZoneVerif.addEventListener('dragover', (e) => { e.preventDefault(); dropZoneVerif.style.backgroundColor = 'var(--text-color)'; dropZoneVerif.style.color = 'var(--bg-color)'; });
    dropZoneVerif.addEventListener('dragleave', () => { dropZoneVerif.style.backgroundColor = ''; dropZoneVerif.style.color = ''; });
    dropZoneVerif.addEventListener('drop', (e) => {
        e.preventDefault(); dropZoneVerif.style.backgroundColor = ''; dropZoneVerif.style.color = '';
        if (e.dataTransfer.files.length) { fileInputVerif.files = e.dataTransfer.files; fileInputVerif.dispatchEvent(new Event('change')); }
    });

    if(btnCancelVerif){
        btnCancelVerif.addEventListener('click', () =>{
            selectedFilesVerif = [];
            dropZoneVerif.innerHTML = `<div class="placeholder-art"><br><p id="depot">[ ? ]</p><br></div>`;
            dropZoneVerif.style.border = "";
            fileStatusVerif.innerText = "en attente...";
            fileInputVerif.value = "";
            const verifContainer = document.getElementById('verif-results-container');
            if (verifContainer) verifContainer.innerHTML = '';
            // Recache le bouton d'export EXIF
            const exifAction = document.getElementById('exif-action-container');
            if (exifAction) exifAction.style.display = 'none';
        });
    }

    if(consoleHeaderTitle){
        consoleHeaderTitle.innerText = tabExplanations[""];
    }

    /*===========TAB WATEMARK=============*/
    
    const consoleWatermark = document.getElementById('console-watermark');

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');

            const tabName = e.target.innerText.trim();
            if (tabExplanations[tabName]){
                consoleHeaderTitle.innerText = tabExplanations[tabName];
            }

            if(consoleWatermark){
                if(tabName === "Watermark"){
                    consoleWatermark.style.display = "block";
                    const firstInput = document.getElementById('watermark-msg');
                    if(firstInput) firstInput.focus();
                }
                else {
                    consoleWatermark.style.display = "none";
                }
            }
        });
    });

    /*===========TAB EXIF=============*/

    const consoleExif = document.getElementById('console-exif');

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');

            const tabName = e.target.innerText.trim();
            if (tabExplanations[tabName]){
                consoleHeaderTitle.innerText = tabExplanations[tabName];
            }

            if(consoleExif){
                if(tabName === "EXIF"){
                    consoleExif.style.display = "block";
                    const firstInput = document.getElementById('exif-auteur');
                    if(firstInput) firstInput.focus();
                }
                else {
                    consoleExif.style.display = "none";
                }
            }
        });
    });


    /*===========TAB STEGANO=============*/
    
    const consoleStegano = document.getElementById('console-stegano');

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');

            const tabName = e.target.innerText.trim();
            if (tabExplanations[tabName]){
                consoleHeaderTitle.innerText = tabExplanations[tabName];
            }

            if(consoleStegano){
                if(tabName === "Stegano"){
                    consoleStegano.style.display = "block";
                    const firstInput = document.getElementById('stegano-msg');
                    if(firstInput) firstInput.focus();
                }
                else {
                    consoleStegano.style.display = "none";
                }
            }
        });
    });

    /*===========TAB SIGNATURE=============*/

    const consoleSign = document.getElementById('console-sign');

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');

            const tabName = e.target.innerText.trim();
            if (tabExplanations[tabName]){
                consoleHeaderTitle.innerText = tabExplanations[tabName];
            }

            if(consoleSign){
                if(tabName === "Signature Num."){
                    consoleSign.style.display = "block";
                    const firstInput = document.getElementById('sign-mdp');
                    if(firstInput) firstInput.focus();
                }
                else {
                    consoleSign.style.display = "none";
                }
            }
        });
    });

    /*===========TAB BLOCKCHAIN=============*/

    const consoleBlock = document.getElementById('console-block');
    const btnExport = document.querySelector('.console-tags .tag');
    const btnNextBlock = document.getElementById('btn-next');

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');

            const tabName = e.target.innerText.trim();
            if (tabExplanations[tabName]){
                consoleHeaderTitle.innerText = tabExplanations[tabName];
            }

            if(consoleBlock){
                if(tabName === "Blockchain OTS"){
                    consoleBlock.style.display = "block";
                    if(btnExport) btnExport.innerText = "[+] Envoyer vers la Blockchain";
                    if(btnNextBlock) btnNextBlock.style.display = "none";
                }
                else {
                    consoleBlock.style.display = "none";
                    if(btnExport) btnExport.innerText = "[E] Exporter";
                    if(btnNextBlock) btnNextBlock.style.display = "inline-block";
                }
            }
        });
    });

    // --- L'effet miroir pour TOUS les curseurs du terminal ---
    const hiddenInputs = document.querySelectorAll('.hidden-terminal-input');

    hiddenInputs.forEach(input => {
        // On cherche automatiquement le miroir qui correspond à l'ID de l'input
        const mirror = document.getElementById(input.id + '-mirror');

        if (mirror) {
            input.addEventListener('input', (e) => {
                // Recopie instantanément le texte tapé
                mirror.textContent = e.target.value;
            });
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
        document.addEventListener('click', () => {
            themeMenu.style.display = 'none';
        });

        // 3. Empêcher la fermeture si on clique à l'intérieur du menu
        themeMenu.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        // 4. Appliquer le thème choisi
        themeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Nettoyer les anciens thèmes
                document.body.classList.remove('theme-blue', 'theme-beige', 'theme-grey');
                
                // Ajouter le nouveau (sauf si on retourne au défaut)
                const selectedTheme = btn.getAttribute('data-theme');
                if (selectedTheme !== 'theme-default') {
                    document.body.classList.add(selectedTheme);
                }

                // --- AJOUT : METTRE À JOUR LE FAVICON ---
                const favicon = document.getElementById('dynamic-favicon');
                if (favicon) {
                    if (selectedTheme === 'theme-default') favicon.href = 'icons/icon-amber.png';
                    if (selectedTheme === 'theme-blue') favicon.href = 'icons/icon-blue.png';
                    if (selectedTheme === 'theme-beige') favicon.href = 'icons/icon-beige.png';
                    if (selectedTheme === 'theme-grey') favicon.href = 'icons/icon-grey.png';
                }
                
                // Fermer le menu
                themeMenu.style.display = 'none';
            });
        });
    }

    // --- GESTION DU BOUTON NEXT ---
    const btnNext = document.getElementById('btn-next');
    
    if (btnNext) {
        btnNext.addEventListener('click', (e) => {
            e.preventDefault();
            
            // 1. Trouver l'onglet actuellement actif
            const activeTab = document.querySelector('.tab.active');
            const tabsArray = Array.from(tabs); // Transforme la NodeList en vrai tableau
            
            if (activeTab) {
                // 2. Trouver sa position (son index)
                const currentIndex = tabsArray.indexOf(activeTab);
                
                // 3. S'il y a un onglet après celui-ci, on simule un clic dessus !
                if (currentIndex < tabsArray.length - 1) {
                    tabsArray[currentIndex + 1].click();
                }
            } else {
                // Si aucun onglet n'est actif par défaut, on active le tout premier
                if (tabsArray.length > 0) {
                    tabsArray[0].click();
                }
            }
        });
    }
    
    fileInputVerif.addEventListener('change', function(){
        const verifContainer = document.getElementById('verif-results-container');
        
        if (this.files && this.files.length > 0) {
            selectedFilesVerif = Array.from(this.files);
            fileStatusVerif.innerText = selectedFilesVerif.length === 1 ? selectedFilesVerif[0].name : `[${selectedFilesVerif.length} FICHIERS ]`;
            
            // Miniature du premier fichier
            const reader = new FileReader();
            reader.onload = function(e) {
                let htmlContent = `<img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover;">`;
                if (selectedFilesVerif.length > 1) {
                    htmlContent += `<div style="position: absolute; bottom: 5px; right: 5px; background: var(--text-color); color: var(--bg-color); padding: 2px 6px; font-weight: bold; border: 1px solid var(--bg-color);">+${selectedFilesVerif.length - 1}</div>`;
                }
                dropZoneVerif.style.position = "relative";
                dropZoneVerif.innerHTML = htmlContent;
                dropZoneVerif.style.border = "none";
            }
            reader.readAsDataURL(selectedFilesVerif[0]);

            // --- NOUVEAU : GÉNÉRATION DES BLOCS DE VÉRIFICATION ---
            if (verifContainer) {
                verifContainer.innerHTML = ''; // On nettoie les anciens rapports

                // Rend le bouton d'export EXIF visible
                const exifAction = document.getElementById('exif-action-container');
                if (exifAction) exifAction.style.display = 'block';
                
                selectedFilesVerif.forEach((file, index) => {
                    // On crée une div "console-panel" pour chaque fichier
                    const fileBlock = document.createElement('div');
                    fileBlock.className = 'console-panel verif-file-block';
                    
                    // On y injecte le HTML avec des IDs indexés (0, 1, 2...)
                    fileBlock.innerHTML = `
                        <div class="console-header">
                            <span>// FICHIER : ${file.name}</span>
                            <span class="verif-result verif-global" id="verif-global-${index}">[ ... ]</span>
                        </div>
                        <div class="console-body">
                            <div class="verif-grid">
                                <div class="verif-item">
                                    <span class="verif-label">> Filigrane (Watermark)</span>
                                    <span class="verif-result" id="res-watermark-${index}">...</span>
                                </div>
                                <div class="verif-item">
                                    <span class="verif-label">> Métadonnées (EXIF)</span>
                                    <span class="verif-result" id="res-exif-${index}">...</span>
                                </div>
                                <div class="verif-item">
                                    <span class="verif-label">> Stéganographie</span>
                                    <span class="verif-result" id="res-stegano-${index}">...</span>
                                </div>
                                <div class="verif-item">
                                    <span class="verif-label">> Signature Numérique</span>
                                    <span class="verif-result" id="res-sign-${index}">...</span>
                                </div>
                            </div>
                        </div>
                    `;
                    verifContainer.appendChild(fileBlock);
                });
            }
        }
    });

});


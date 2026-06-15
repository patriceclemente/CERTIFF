document.addEventListener('DOMContentLoaded', () => {
    
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
            const targetMenu = e.target.innerText.trim();

            if (targetMenu === "Vérification") {
                if(panelCertif) panelCertif.style.display = "none";
                if(panelVerif) panelVerif.style.display = "block";
            } else if (targetMenu === "Certification") {
                if(panelVerif) panelVerif.style.display = "none";
                if(panelCertif) panelCertif.style.display = "block";
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
        "Certif complète" : "[MODE : CERTIF COMPLÈTE] Pipeline complète de certification.",
        "Watermark" : "[MODE : WARTERMARK] Incrustation d'un filigrane visible.",
        "EXIF" : "[MODE : EXIF] Injection de métadonnées d'identification.",
        "Stegano" : "[MODE : STEGANO] Insertion de métadonnées invisibles.",
        "Signature Num." : "[MODE : SIGNATURE] Chiffrement asymétrique pour authentification d'identité.",
        "Blockachain OTS" : "[MODE : BLOCKCHAIN] Horodatage et preuve."
    }

    if(consoleHeaderTitle){
        consoleHeaderTitle.innerText = tabExplanations["Certif complète"];
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
        });
    }

    if(consoleHeaderTitle){
        consoleHeaderTitle.innerText = tabExplanations["Certif complète"];
    }

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
                }
                else {
                    consoleStegano.style.display = "none";
                }
            }
        });
    });

});


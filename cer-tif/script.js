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
            
            // Simule un changement dans la console en fonction de l'onglet cliqué
            updateConsoleContent(e.target.innerText);
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
        "Certif complète" : "[MODE : CERTIF COMPLETE] Pipeline complète de certification.",
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
});


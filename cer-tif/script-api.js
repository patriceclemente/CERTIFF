document.addEventListener('DOMContentLoaded', () => {

    fetch('/api/config')
    .then(response => response.json())
    .then(config => {
        console.log("CONFIG RECUE :", config);

        /*
        document.getElementById('watermark-msg').value = config.wm_text;
        document.getElementById('watermark-taillep').value = config.wm_pointsize;
        document.getElementById('watermark-couleur').value = config.wm_color;
        document.getElementById('watermark-opacite').value = config.wm_opacity;
        document.getElementById('watermark-angle').value = config.wm_angle;
        document.getElementById('watermark-espace').value = config.wm_spacing;

        document.getElementById('stegano-msg').value = config.stegano_message;

        document.getElementById('exif-auteur').value = config.exif_artist;
        document.getElementById('exif-copy').value = config.exif_copyright;
        document.getElementById('exif-date').value = config.exif_date || ""; 
        // ICI
        */

        document.getElementById('watermark-defaults').innerHTML = `
            <li>${config.wm_text}</li>
            <li>${config.wm_pointsize}</li>
            <li>${config.wm_color}</li>
            <li>${config.wm_opacity}</li>
            <li>${config.wm_angle}</li>
            <li>${config.wm_spacing}</li>
        `;
        document.getElementById('stegano-defaults').innerHTML = `
            <li>${config.stegano_message}</li>
            <li>defaut</li>
        `;

        document.getElementById('exif-defaults').innerHTML = `
            <li>${config.exif_artist}</li>
            <li>${config.exif_copyright}</li>
            <li>${config.exif_date || "Date actuelle"}</li>
        `;  
        

        // mise à jour des miroirs terminal
        document.querySelectorAll('.terminal-mirror').forEach(mirror => {
            const id = mirror.id.replace("-mirror", "");
            const input = document.getElementById(id);
            if (input) {
                mirror.textContent = input.value;
            }
        });

    })
    .catch(error => console.error("Erreur chargement config :", error));

    // ---------------------------------------------------------
    //  Outils de rendu du rapport d'audit
    // ---------------------------------------------------------
    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function statusFromLines(lines) {
        if (lines.some(line => line.includes("[ERROR]") || line.includes("[ERREUR]"))) {
            return { label: "ECHEC", className: "error" };
        }
        if (lines.some(line => line.includes("[WARN]") || line.includes("introuvable") || line.includes("aucune info"))) {
            return { label: "INCOMPLET", className: "warn" };
        }
        if (lines.some(line => line.includes("[OK]"))) {
            return { label: "VALIDE", className: "ok" };
        }
        return { label: "INFO", className: "info" };
    }

    function splitAuditSections(lines) {
        const sections = [
            { key: "stegano", title: "Steganographie", icon: "[S]", markers: ["filigrane invisible"], lines: [] },
            { key: "signature", title: "Signature numerique", icon: "[SIG]", markers: ["signature numerique", "signature numérique"], lines: [] },
            { key: "blockchain", title: "Blockchain OTS", icon: "[OTS]", markers: ["blockchain"], lines: [] },
            { key: "exif", title: "Metadonnees EXIF", icon: "[EXIF]", markers: ["exif", "File Type", "MIME Type", "Image Width", "Image Height", "Image Size", "Artist", "Creator", "Copyright", "Date"], lines: [] }
        ];

        let current = null;
        lines.forEach(rawLine => {
            const line = String(rawLine || "").trim();
            if (!line || line.includes("Rapport final") || line.includes("Verification des dependances") || line.includes("Dependances pretes") || line.includes("[ACTION]")) {
                return;
            }
            if (line.includes("Extraction avec -p")) {
                return;
            }

            const lower = line.toLowerCase();
            const matched = sections.find(section =>
                section.markers.some(marker => lower.includes(marker.toLowerCase()))
            );

            if (line.startsWith("===") && matched) {
                current = matched;
                return;
            }
            if (matched && matched.key === "exif" && !line.startsWith("===")) {
                matched.lines.push(line);
                current = matched;
                return;
            }
            if (current) current.lines.push(line);
        });

        return sections;
    }

    function renderAuditReport(lines) {
        const sections = splitAuditSections(lines);
        const globalStatus = statusFromLines(lines);

        return `
            <div class="audit-report">
                <div class="audit-header">
                    <span>[RAPPORT D'AUDIT TECHNIQUE]</span>
                    <span class="audit-pill ${globalStatus.className}">${globalStatus.label}</span>
                </div>
                <div class="audit-grid">
                    ${sections.map(section => {
                        const sectionStatus = statusFromLines(section.lines);
                        const details = section.lines.length
                            ? section.lines.map(line => `<li>${escapeHtml(line)}</li>`).join('')
                            : '<li>Aucune donnee disponible pour cette etape.</li>';
                        return `
                            <article class="audit-card ${sectionStatus.className}">
                                <div class="audit-card-title">
                                    <span>${section.icon} ${section.title}</span>
                                    <span class="audit-pill ${sectionStatus.className}">${sectionStatus.label}</span>
                                </div>
                                <ul class="audit-lines">${details}</ul>
                            </article>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    // ---------------------------------------------------------
    //  Elements pipeline certification
    // ---------------------------------------------------------
    const fileInput = document.getElementById('file-upload');
    const dropZone = document.querySelector('.image-preview');
    const btnExecute = document.querySelector('.console-footer span:first-child');
    const btnExport = document.querySelector('.console-tags .tag');
    const btnNext = document.getElementById('btn-next');
    const tabs = document.querySelectorAll('.tab');

    let currentCertifStep = 0; // 0:Watermark 1:EXIF 2:Stegano 3:Signature 4:Blockchain
    let currentDownloadUrl = "";

    // Reinitialiser le parcours quand l'image change
    if (fileInput) {
        fileInput.addEventListener('change', () => {
            currentCertifStep = 0;
            window.currentDepotId = null;
            console.log("Nouvelle image detectee. Stepper reinitialise a l'etape 0.");
        });
    }

    // ---------------------------------------------------------
    //  Envoi d'une etape du pipeline a Flask
    //  IMPORTANT : cet appel NE sauvegarde PAS en base de donnees.
    //  La sauvegarde est faite par /api/upload (script.js, clic [Importer]).
    // ---------------------------------------------------------
    function ensureDepotBeforePipeline() {
        if (window.currentDepotId) {
            return Promise.resolve(window.currentDepotId);
        }
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            return Promise.reject(new Error("Aucune image importee."));
        }

        const uploadData = new FormData();
        uploadData.append('file', fileInput.files[0]);
        return fetch('/api/upload', { method: 'POST', body: uploadData })
            .then(response => response.json())
            .then(data => {
                if (data.status !== "success") {
                    throw new Error(data.message || "Depot impossible.");
                }
                if (data.depot_id) {
                    window.currentDepotId = data.depot_id;
                }
                return window.currentDepotId;
            });
    }

    function executerEtapePipeline(apiAction, nomEtapeAffichage, isNextClick = false) {
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            alert("Veuillez d'abord importer une image via la zone [ + ].");
            return;
        }

        const formData = new FormData();
        formData.append('action', apiAction);
        formData.append('file', fileInput.files[0]);

        const wmText = document.getElementById('watermark-msg')?.value.trim();
        const wmSize = document.getElementById('watermark-taillep')?.value.trim();
        const wmColor = document.getElementById('watermark-couleur')?.value.trim();
        const wmOpacity = document.getElementById('watermark-opacite')?.value.trim();
        const wmAngle = document.getElementById('watermark-angle')?.value.trim();
        const wmSpacing = document.getElementById('watermark-espace')?.value.trim();
        const steganoMessage = document.getElementById('stegano-msg')?.value.trim();
        const exifArtist = document.getElementById('exif-auteur')?.value.trim();
        const exifCopyright = document.getElementById('exif-copy')?.value.trim();
        const exifDate = document.getElementById('exif-date')?.value.trim();
        
        if (wmText) formData.append('wm_text', wmText);
        if (wmSize) formData.append('wm_size', wmSize);
        if (wmColor) formData.append('wm_color', wmColor);
        if (wmOpacity) formData.append('wm_opacity', wmOpacity);
        if (wmAngle) formData.append('wm_angle', wmAngle);
        if (wmSpacing) formData.append('wm_spacing', wmSpacing);
        if (steganoMessage) formData.append('stegano_message', steganoMessage);
        if (exifArtist) formData.append('exif_artist', exifArtist);
        if (exifCopyright) formData.append('exif_copyright', exifCopyright);
        if (exifDate) formData.append('exif_date', exifDate);
        
        /*         formData.append('wm_text', wmText || "© Cert-Art.fr");
        formData.append('wm_size', wmSize || "35");
        formData.append('wm_color', wmColor || "128,128,128");
        formData.append('wm_opacity', wmOpacity || "0.2");
        formData.append('wm_angle', wmAngle || "-45");
        formData.append('wm_spacing', wmSpacing || "300");
        formData.append('stegano_message', document.getElementById('stegano-msg')?.value || "defaut");
        formData.append('exif_artist', document.getElementById('exif-auteur')?.value || "");
        formData.append('exif_copyright', document.getElementById('exif-copy')?.value || "");
        formData.append('exif_date', document.getElementById('exif-date')?.value || ""); */

        formData.append('depot_id', window.currentDepotId || "");

        if (btnExecute) btnExecute.innerText = "[...] Calcul...";
        if (btnNext) btnNext.innerText = "[...] Calcul...";

        console.log(`[Etape ${currentCertifStep + 1}] Envoi de l'action : ${apiAction}`);

        ensureDepotBeforePipeline()
            .then(() => {
                formData.set('depot_id', window.currentDepotId || "");
                return fetch('/api', { method: 'POST', body: formData });
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    if (data.image_base64) {
                        currentDownloadUrl = data.image_base64;
                        if (dropZone) {
                            dropZone.innerHTML = `<img src="${data.image_base64}" style="width:100%;height:100%;object-fit:cover;border:2px solid #ff9f00;">`;
                        }
                    }
                    if (isNextClick) currentCertifStep++;
                    alert(`Succes : ${nomEtapeAffichage} valide. Etape suivante prete.`);
                } else {
                    const details = Array.isArray(data.terminal_output)
                        ? "\n\n" + data.terminal_output.slice(-6).join("\n")
                        : "";
                    alert(`Erreur au cours de l'etape : ${data.message}${details}`);
                }
                if (btnNext) btnNext.innerText = "[N] Next ";
                if (btnExecute) btnExecute.innerText = "[↵] Executer";
            })
            .catch(error => {
                console.error("Erreur reseau :", error);
                alert("Erreur de communication avec le serveur Flask.");
                if (btnNext) btnNext.innerText = "[N] Next ";
                if (btnExecute) btnExecute.innerText = "[↵] Executer";
            });
    }

    function basculerVisualisationOnglet(nomOnglet, idConsole) {
        tabs.forEach(tab => tab.classList.toggle('active', tab.innerText.trim() === nomOnglet));
        ['console-watermark', 'console-exif', 'console-stegano', 'console-sign', 'console-block'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = (id === idConsole) ? 'block' : 'none';
        });
    }

    // ---------------------------------------------------------
    //  Bouton [N] Next : pipeline sequentiel
    // ---------------------------------------------------------
    if (btnNext) {
        btnNext.addEventListener('click', (e) => {
            e.preventDefault();
            if (currentCertifStep === 0) {
                basculerVisualisationOnglet("Watermark", "console-watermark");
                executerEtapePipeline("visible", "Etape 1/5 : Filigrane Visible", true);
            } else if (currentCertifStep === 1) {
                basculerVisualisationOnglet("EXIF", "console-exif");
                executerEtapePipeline("exif", "Etape 2/5 : Metadonnees EXIF", true);
            } else if (currentCertifStep === 2) {
                basculerVisualisationOnglet("Stegano", "console-stegano");
                executerEtapePipeline("stegano", "Etape 3/5 : Filigrane Invisible (Steganographie)", true);
            } else if (currentCertifStep === 3) {
                basculerVisualisationOnglet("Signature Num.", "console-sign");
                executerEtapePipeline("signature", "Etape 4/5 : Signature Numerique", true);
            } else if (currentCertifStep === 4) {
                basculerVisualisationOnglet("Blockchain OTS", "console-block");
                executerEtapePipeline("blockchain", "Etape 5/5 : Horodatage Blockchain OTS", true);
            } else {
                alert("Certification 100% complete. Vous pouvez exporter l'image definitive.");
            }
        });
    }

    // ---------------------------------------------------------
    //  Bouton [Exécuter] : action unitaire selon l'onglet actif
    // ---------------------------------------------------------
    if (btnExecute) {
        btnExecute.style.cursor = 'pointer';
        btnExecute.addEventListener('click', (e) => {
            e.preventDefault();
            const activeTab = document.querySelector('.tab.active');
            const tabName = activeTab ? activeTab.innerText.trim() : "";

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
            } else {
                alert("Selectionnez un onglet de certification, ou utilisez [N] Next pour le pipeline complet.");
            }
        });
    }

    // ---------------------------------------------------------
    //  Bouton [E] Exporter
    // ---------------------------------------------------------
    if (btnExport) {
        btnExport.style.cursor = 'pointer';
        btnExport.addEventListener('click', (e) => {
            e.preventDefault();
            if (!currentDownloadUrl) {
                alert("Aucune image traitee disponible pour l'export.");
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

    // ---------------------------------------------------------
    //  Zone VERIFICATION : lancement du rapport d'audit.
    //  (apercu / import / annuler / drag&drop sont geres dans script.js)
    // ---------------------------------------------------------
    const fileInputVerif = document.getElementById('file-upload-verif');
    const resultsContainer = document.getElementById('verif-results-container');
    const statusVerifText = document.getElementById('file-status-verif');

    if (fileInputVerif) {
        fileInputVerif.addEventListener('change', () => {
            if (fileInputVerif.files.length === 0) return;
            const file = fileInputVerif.files[0];
            if (statusVerifText) statusVerifText.innerText = "Analyse en cours...";

            const formData = new FormData();
            formData.append('action', 'report');
            formData.append('file', file);

            fetch('/api', { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    if (statusVerifText) statusVerifText.innerText = "Terminee";
                    if (data.status === "success" && data.terminal_output) {
                        resultsContainer.innerHTML = renderAuditReport(data.terminal_output);
                    } else {
                        resultsContainer.innerHTML = `<p style="color:red;font-family:monospace;">Erreur lors de l'audit : ${escapeHtml(data.message || "Erreur inconnue")}</p>`;
                    }
                })
                .catch(() => {
                    if (statusVerifText) statusVerifText.innerText = "Echec connexion";
                    alert("Impossible de joindre le serveur Flask pour lancer le rapport d'audit.");
                });
        });
    }
});

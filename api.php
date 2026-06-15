<?php
// -------------------------------------------------------------------------
// api.php - Contrôleur REST pour le script de protection d'images
// Fait le lien entre l'IHM (JS/Fetch) et le moteur d'action Bash portable
// -------------------------------------------------------------------------

// entêtes : sécurité, format de réponse JSON
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: POST, GET, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

// gestion de la requête de pré-vérification du navigateur (OPTIONS)
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

// Dossier local temporaire pour réceptionner les téléversements
$uploadDir = 'uploads/';
if (!is_dir($uploadDir)) {
    mkdir($uploadDir, 0777, true);
}

// 1. Récupération de l'action atomique demandée
$action = $_GET['action'] ?? $_POST['action'] ?? '';

// Liste des actions supportées par le script
$allowedActions = [
    'visible', 'exif', 'stegano', 'signature', 'blockchain', 
    'check_stegano', 'check_signature', 'check_blockchain', 
    'show_exif', 'report', 'pipeline'
];

if (empty($action) || !in_array($action, $allowedActions)) {
    echo json_encode([
        "status" => "error", 
        "message" => "Action manquante ou inconnue. Actions valides : " . implode(', ', $allowedActions)
    ]);
    exit;
}

// 2. Gestion du fichier image (Stateless / Atomique)
$inputImgPath = '';
$fileName = '';

if (isset($_FILES['file']) && $_FILES['file']['error'] === UPLOAD_ERR_OK) {
    // Cas A : L'IHM envoie un nouveau fichier physique (ex: à l'étape du filigrane visible)
    $fileName = basename($_FILES['file']['name']);
    $targetFilePath = $uploadDir . $fileName;
    if (move_uploaded_file($_FILES['file']['tmp_name'], $targetFilePath)) {
        $inputImgPath = $targetFilePath;
    }
} else {
    // Cas B : Pas de fichier brut envoyé (ex: pour une étape suivante comme 'exif' ou 'blockchain').
    // On réutilise le nom du fichier précédemment stocké dans 'uploads/' envoyé par le JS
    $fileName = $_POST['filename'] ?? $_GET['filename'] ?? '';
    if (!empty($fileName)) {
        $inputImgPath = $uploadDir . basename($fileName);
    }
}

// Sécurité : Une image existante est indispensable pour exécuter le script
if (empty($inputImgPath) || !file_exists($inputImgPath)) {
    echo json_encode([
        "status" => "error",
        "message" => "Fichier image introuvable. Veuillez téléverser un fichier ou passer un 'filename' valide."
    ]);
    exit;
}

// 3. Collecte dynamique des paramètres optionnels de l'IHM
$options = [];

// Options de Filigrane Visible
if (!empty($_POST['wm_mode']))    $options[] = "--wm-mode " . escapeshellarg($_POST['wm_mode']);
if (!empty($_POST['wm_text']))    $options[] = "--wm-text " . escapeshellarg($_POST['wm_text']);
if (!empty($_POST['wm_spacing'])) $options[] = "--wm-spacing " . escapeshellarg($_POST['wm_spacing']);
if (!empty($_POST['wm_size']))    $options[] = "--wm-size " . escapeshellarg($_POST['wm_size']);
if (!empty($_POST['wm_opacity'])) $options[] = "--wm-opacity " . escapeshellarg($_POST['wm_opacity']);
if (!empty($_POST['wm_color']))   $options[] = "--wm-color " . escapeshellarg($_POST['wm_color']);
if (!empty($_POST['wm_angle']))   $options[] = "--wm-angle " . escapeshellarg($_POST['wm_angle']);
if (!empty($_POST['wm_font']))    $options[] = "--wm-font " . escapeshellarg($_POST['wm_font']);

// Options de Stéganographie
if (!empty($_POST['stegano_message'])) $options[] = "--stegano-message " . escapeshellarg($_POST['stegano_message']);

// Option de date personnalisée pour l'EXIF (passée en 3ème argument positionnel dans le Bash)
$exifDateArg = "";
if ($action === 'exif' && !empty($_POST['exif_date'])) {
    $exifDateArg = " " . escapeshellarg($_POST['exif_date']);
}

// On assemble les options facultatives sous forme de chaîne
$optionsStr = implode(" ", $options);

// 4. Construction de la commande exacte attendue par le script de Patrice Clemente
// Format : bash protect_image.sh [options] [action] [base_dir] [image_path] [exif_date]
$command = "bash ./protect_image.sh " . 
           $optionsStr . " " . 
           escapeshellarg($action) . " . " . 
           escapeshellarg($inputImgPath) . 
           $exifDateArg . " 2>&1"; // Capturer stderr et stdout

// 5. Exécution de la commande système locale
exec($command, $output, $returnCode);

// 6. Envoi de la réponse structurée en JSON au JavaScript
if ($returnCode === 0) {
    echo json_encode([
        "status" => "success",
        "action_executed" => $action,
        "filename" => $fileName,
        "message" => "L'action atomique [ $action ] s'est exécutée avec succès.",
        "terminal_output" => $output
    ]);
} else {
    http_response_code(500);
    echo json_encode([
        "status" => "error",
        "action_executed" => $action,
        "message" => "Le moteur de traitement Bash a rencontré une erreur.",
        "error_code" => $returnCode,
        "terminal_output" => $output
    ]);
}
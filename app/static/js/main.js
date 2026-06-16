// main.js — JS global de VaultGG, chargé sur toutes les pages via base.html.

// DOMContentLoaded : on attend que le HTML soit entièrement parsé avant de
// chercher les éléments. Sinon, si le script s'exécute avant que le bouton
// existe, getElementById renvoie null et l'écouteur n'est jamais posé.
document.addEventListener("DOMContentLoaded", function () {
    const formHltb = document.getElementById("form-hltb");

    // Garde : le form HLTB n'existe que si l'utilisateur est connecté. Sur les
    // pages où il est absent, on ne fait rien (évite une erreur sur null).
    if (formHltb) {
        formHltb.addEventListener("submit", function () {
            // Spinner + désactivation au submit : signale le travail en cours
            // (passe de plusieurs minutes) et empêche le double-clic.
            document.getElementById("spinner-hltb").classList.remove("d-none");
            document.getElementById("label-hltb").textContent = "Récupération…";
            document.getElementById("btn-hltb").disabled = true;
        });
    }
});
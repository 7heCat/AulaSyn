// ======================================================
// 1. INICIALIZACIÓN
// ======================================================

document.addEventListener("DOMContentLoaded", iniciarAplicacion);

function iniciarAplicacion() {
    mostrarVista("login");
    iniciarEventos();
}


// ======================================================
// 2. NAVEGACIÓN ENTRE VISTAS
// ======================================================

function mostrarVista(tipoVista) {
    const vistas = document.querySelectorAll(".vista-autenticacion");

    const mensajes = {
        login: "Herramienta basada en técnicas computacionales de inteligencia artificial para la asignación de horarios, salones y docentes del programa de Ingeniería en Sistemas.",
        registro: "Regístrate para acceder a la plataforma y gestionar la información académica del programa de Ingeniería en Sistemas.",
        recuperacion: "Mantén tu información personal y académica actualizada para el correcto funcionamiento de AULASYN."
    };

    vistas.forEach(function (vista) {
        vista.hidden = vista.id !== "vista-" + tipoVista;
    });

    const mensajePanel = document.getElementById("mensaje-panel");

    if (mensajePanel && mensajes[tipoVista]) {
        mensajePanel.textContent = mensajes[tipoVista];
    }
}


// ======================================================
// 3. SELECCIÓN DEL ROL
// ======================================================

function seleccionarRol(rol) {
    const campoRol = document.getElementById("rol-registro");
    const opciones = document.querySelectorAll(".opcion-rol");

    if (!campoRol || !["estudiante", "profesor"].includes(rol)) {
        return;
    }

    campoRol.value = rol;

    opciones.forEach(function (opcion) {
        const seleccionada = opcion.dataset.rol === rol;

        opcion.classList.toggle("seleccionada", seleccionada);
        opcion.setAttribute("aria-pressed", String(seleccionada));
    });
}


// ======================================================
// 4. VALIDACIONES GENERALES
// ======================================================

function validarCorreo(campo) {
    if (!campo || !campo.value.trim()) {
        alert("Ingresa tu correo institucional.");

        if (campo) {
            campo.focus();
        }

        return false;
    }

    if (!campo.checkValidity()) {
        alert("Ingresa un correo con formato válido.");
        campo.focus();
        return false;
    }

    return true;
}


function validarLongitudContrasena(campo) {
    if (campo.value.length < 8) {
        alert("La contraseña debe tener al menos 8 caracteres.");
        campo.focus();
        return false;
    }

    return true;
}


// ======================================================
// 5. INICIO DE SESIÓN
// Pendiente para una historia de usuario posterior.
// ======================================================

function iniciarSesion() {
    const correo = document.getElementById("correo-login");
    const contrasena = document.getElementById("contrasena-login");

    if (!validarCorreo(correo)) {
        return;
    }

    if (!contrasena.value) {
        alert("Ingresa tu contraseña.");
        contrasena.focus();
        return;
    }

    alert(
        "El inicio de sesión se conectará en una historia de usuario posterior."
    );
}


// ======================================================
// 6. REGISTRO DE USUARIO - HU1
// ======================================================

function validarRegistro() {
    const nombres = document.getElementById("nombres");
    const apellidos = document.getElementById("apellidos");
    const correo = document.getElementById("correo-registro");
    const documento = document.getElementById("documento");
    const contrasena = document.getElementById("contrasena-registro");
    const confirmar = document.getElementById("confirmar-contrasena");
    const terminos = document.getElementById("acepta-terminos");
    const rol = document.getElementById("rol-registro").value;

    const campos = [
        nombres,
        apellidos,
        correo,
        documento,
        contrasena,
        confirmar
    ];

    for (const campo of campos) {
        if (!campo.value.trim()) {
            alert("Completa todos los campos del registro.");
            campo.focus();
            return false;
        }
    }

    if (!validarCorreo(correo)) {
        return false;
    }

    if (!validarLongitudContrasena(contrasena)) {
        return false;
    }

    if (contrasena.value !== confirmar.value) {
        alert("Las contraseñas no coinciden.");
        confirmar.focus();
        return false;
    }

    if (!terminos.checked) {
        alert("Debes aceptar los términos y las políticas de privacidad.");
        terminos.focus();
        return false;
    }

    // Validación inicial del dominio en el navegador.
    // El servidor también realiza esta comprobación.
    const correoNormalizado = correo.value.trim().toLowerCase();

    const dominios = {
        estudiante: "@estudiante.uniajc.edu.co",
        profesor: "@profesores.uniajc.edu.co"
    };

    if (!dominios[rol] || !correoNormalizado.endsWith(dominios[rol])) {
        if (rol === "profesor") {
            alert(
                "Para registrarte como profesor, utiliza tu correo institucional @profesores.uniajc.edu.co."
            );
        } else {
            alert(
                "Para registrarte como estudiante, utiliza tu correo institucional @estudiante.uniajc.edu.co."
            );
        }

        correo.focus();
        return false;
    }

    return true;
}



async function registrarUsuario() {
    if (!validarRegistro()) {
        return;
    }

    const boton = document.getElementById("registrar");
    const textoOriginal = boton.innerText;

    const datosUsuario = {
        nombres: document.getElementById("nombres").value.trim(),
        apellidos: document.getElementById("apellidos").value.trim(),
        correo: document.getElementById("correo-registro").value.trim().toLowerCase(),
        documento: document.getElementById("documento").value.trim(),
        contrasena: document.getElementById("contrasena-registro").value,
        rol: document.getElementById("rol-registro").value,
        acepta_terminos: document.getElementById("acepta-terminos").checked
    };

    boton.disabled = true;
    boton.innerText = "Creando cuenta...";

    try {
        const respuesta = await fetch("/api/registro", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(datosUsuario)
        });

        const resultado = await respuesta.json();

        if (!respuesta.ok) {
            if (respuesta.status === 409) {
                alert("Ya existe una cuenta con ese correo o documento.");
            } else {
                alert(resultado.mensaje || "No fue posible crear la cuenta.");
            }
            return;
        }

        alert(resultado.mensaje);

        document.getElementById("nombres").value = "";
        document.getElementById("apellidos").value = "";
        document.getElementById("correo-registro").value = "";
        document.getElementById("documento").value = "";
        document.getElementById("contrasena-registro").value = "";
        document.getElementById("confirmar-contrasena").value = "";
        document.getElementById("acepta-terminos").checked = false;

        seleccionarRol("estudiante");
        mostrarVista("login");

    } catch (error) {
        console.error("Error durante el registro:", error);

        alert(
            "Ocurrió un problema al procesar la respuesta del servidor. " +
            "Revisa la consola del navegador para conocer el detalle."
        );

    } finally {
        boton.disabled = false;
        boton.innerText = textoOriginal;
    }
}



// ======================================================
// 7. RECUPERACIÓN DE CONTRASEÑA
// Pendiente para una historia de usuario posterior.
// ======================================================

function enviarCodigoRecuperacion() {
    const correo = document.getElementById("correo-recuperacion");

    if (!validarCorreo(correo)) {
        return;
    }

    alert(
        "La recuperación de contraseña se conectará en una historia de usuario posterior."
    );
}


function validarRecuperacion() {
    const correo = document.getElementById("correo-recuperacion");
    const codigo = document.getElementById("codigo-recuperacion");
    const nueva = document.getElementById("nueva-contrasena");
    const confirmar = document.getElementById("confirmar-nueva-contrasena");

    if (!validarCorreo(correo)) {
        return false;
    }

    if (!codigo.value.trim()) {
        alert("Ingresa el código de verificación.");
        codigo.focus();
        return false;
    }

    if (!nueva.value || !confirmar.value) {
        alert("Completa los dos campos de contraseña.");
        nueva.focus();
        return false;
    }

    if (!validarLongitudContrasena(nueva)) {
        return false;
    }

    if (nueva.value !== confirmar.value) {
        alert("Las contraseñas no coinciden.");
        confirmar.focus();
        return false;
    }

    return true;
}


function restablecerContrasena() {
    if (!validarRecuperacion()) {
        return;
    }

    alert(
        "La recuperación de contraseña se conectará en una historia de usuario posterior."
    );
}


// ======================================================
// 8. CONFIGURACIÓN DE EVENTOS
// ======================================================

function iniciarEventos() {
    document.getElementById("ir-registro").addEventListener(
        "click",
        function () {
            mostrarVista("registro");
        }
    );

    document.getElementById("ir-recuperacion").addEventListener(
        "click",
        function () {
            mostrarVista("recuperacion");
        }
    );

    document.getElementById("volver-login-registro").addEventListener(
        "click",
        function () {
            mostrarVista("login");
        }
    );

    document.getElementById("volver-login-recuperacion").addEventListener(
        "click",
        function () {
            mostrarVista("login");
        }
    );

    document.getElementById("ingresar").addEventListener(
        "click",
        iniciarSesion
    );

    document.getElementById("registrar").addEventListener(
        "click",
        registrarUsuario
    );

    document.getElementById("enviar-codigo").addEventListener(
        "click",
        enviarCodigoRecuperacion
    );

    document.getElementById("guardar-contrasena").addEventListener(
        "click",
        restablecerContrasena
    );

    document.querySelectorAll(".opcion-rol").forEach(function (opcion) {
        opcion.addEventListener("click", function () {
            seleccionarRol(opcion.dataset.rol);
        });
    });

    seleccionarRol("estudiante");
}
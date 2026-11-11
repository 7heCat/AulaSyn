
/* =========================================
   SISTEMA DE MODALES Y NOTIFICACIONES
   AULASYN
========================================= */

document.addEventListener("DOMContentLoaded", function () {

    const fondoModal = document.getElementById("modal-fondo");
    const tituloModal = document.getElementById("modal-titulo");
    const mensajeModal = document.getElementById("modal-mensaje");
    const iconoModal = document.getElementById("modal-icono");
    const botonCancelar = document.getElementById("modal-cancelar");
    const botonConfirmar = document.getElementById("modal-confirmar");
    const contenedorNotificaciones =
        document.getElementById("contenedor-notificaciones");

    let resolverModal = null;

    // =====================================
    // ABRIR VENTANA DE CONFIRMACIÓN
    // =====================================

    function confirmarAccion(opciones = {}) {

        return new Promise(function (resolve) {

            resolverModal = resolve;

            tituloModal.textContent =
                opciones.titulo || "Confirmar acción";

            mensajeModal.textContent =
                opciones.mensaje || "¿Deseas continuar?";

            iconoModal.textContent =
                opciones.icono || "?";

            iconoModal.className =
                "modal-icono " + (opciones.tipo || "informacion");

            botonCancelar.textContent =
                opciones.textoCancelar || "Cancelar";

            botonConfirmar.textContent =
                opciones.textoConfirmar || "Confirmar";

            botonConfirmar.className =
                "modal-boton " +
                (opciones.botonPeligro ? "peligro" : "confirmar");

            fondoModal.classList.add("visible");
            fondoModal.setAttribute("aria-hidden", "false");

            botonConfirmar.focus();

        });

    }

    // =====================================
    // CERRAR VENTANA
    // =====================================

    function cerrarModal(resultado) {

        if (!fondoModal.classList.contains("visible")) {
            return;
        }

        fondoModal.classList.remove("visible");
        fondoModal.setAttribute("aria-hidden", "true");

        if (resolverModal) {
            resolverModal(resultado);
            resolverModal = null;
        }

    }

    botonCancelar.addEventListener("click", function () {
        cerrarModal(false);
    });

    botonConfirmar.addEventListener("click", function () {
        cerrarModal(true);
    });

    fondoModal.addEventListener("click", function (evento) {

        if (evento.target === fondoModal) {
            cerrarModal(false);
        }

    });

    document.addEventListener("keydown", function (evento) {

        if (evento.key === "Escape") {
            cerrarModal(false);
        }

    });

    // =====================================
    // MOSTRAR NOTIFICACIONES
    // =====================================

    function mostrarNotificacion(mensaje, tipo = "informacion") {

        const configuracion = {
            exito: {
                icono: "✓"
            },
            error: {
                icono: "✕"
            },
            advertencia: {
                icono: "!"
            },
            informacion: {
                icono: "i"
            }
        };

        const datos = configuracion[tipo] || configuracion.informacion;

        const notificacion = document.createElement("div");
        notificacion.className = "notificacion-aulasyn " + tipo;

        const icono = document.createElement("span");
        icono.className = "notificacion-icono";
        icono.textContent = datos.icono;

        const texto = document.createElement("div");
        texto.className = "notificacion-texto";
        texto.textContent = mensaje;

        const botonCerrar = document.createElement("button");
        botonCerrar.className = "notificacion-cerrar";
        botonCerrar.type = "button";
        botonCerrar.textContent = "×";
        botonCerrar.setAttribute("aria-label", "Cerrar notificación");

        notificacion.appendChild(icono);
        notificacion.appendChild(texto);
        notificacion.appendChild(botonCerrar);

        contenedorNotificaciones.appendChild(notificacion);

        function retirarNotificacion() {

            if (!notificacion.isConnected) {
                return;
            }

            notificacion.classList.add("saliendo");

            setTimeout(function () {
                notificacion.remove();
            }, 200);

        }

        botonCerrar.addEventListener("click", retirarNotificacion);

        setTimeout(retirarNotificacion, 4500);

    }

    // =====================================
    // FUNCIONES DISPONIBLES PARA LOS MÓDULOS
    // =====================================

    window.AulaSynModal = {
        confirmar: confirmarAccion,
        notificar: mostrarNotificacion
    };

});

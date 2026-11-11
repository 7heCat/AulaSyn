document.addEventListener("DOMContentLoaded", () => {

    // =====================================================
    // ELEMENTOS HU5: DISPONIBILIDAD
    // =====================================================

    const modal = document.getElementById("modal-disponibilidad");
    const formulario = document.getElementById("form-disponibilidad");
    const botonAbrirModal = document.getElementById("abrir-modal-disponibilidad");
    const botonCerrarModal = document.getElementById("cerrar-modal-disponibilidad");
    const botonCancelar = document.getElementById("cancelar-disponibilidad");
    const botonGuardar = document.getElementById("guardar-disponibilidad");

    const selectDocente = document.getElementById("disponibilidad-docente");
    const selectDia = document.getElementById("disponibilidad-dia");
    const selectSede = document.getElementById("disponibilidad-sede");
    const selectFranja = document.getElementById("disponibilidad-franja");
    const selectAsignatura = document.getElementById("disponibilidad-asignatura");

    const tablaDisponibilidad = document.getElementById("tabla-disponibilidad");
    const buscarDocente = document.getElementById("buscar-docente");
    const filtroSede = document.getElementById("filtro-sede");
    const filtroDia = document.getElementById("filtro-dia");

    // =====================================================
    // ELEMENTOS HU6: DOCENTES Y ASIGNATURAS
    // =====================================================

    const buscarDocenteHU6 = document.getElementById("buscar-docente-hu6");
    const tablaDocentesHU6 = document.getElementById("tabla-docentes-hu6");
    const tablaAsignaciones = document.getElementById("tabla-docente-asignaturas");

    const modalEditar = document.getElementById("modal-editar-docente");
    const formularioEditar = document.getElementById("form-editar-docente");
    const editarIdDocente = document.getElementById("editar-id-docente");
    const editarNombres = document.getElementById("editar-nombres");
    const editarApellidos = document.getElementById("editar-apellidos");
    const editarCorreo = document.getElementById("editar-correo");
    const editarDocumento = document.getElementById("editar-documento");
    const cerrarModalEditar = document.getElementById("cerrar-modal-editar-docente");
    const cancelarEditar = document.getElementById("cancelar-editar-docente");
    const guardarEditar = document.getElementById("guardar-editar-docente");

    const modalAsignatura = document.getElementById("modal-asignatura");
    const formularioAsignatura = document.getElementById("form-asociar-asignatura");
    const selectDocenteAsignatura = document.getElementById("asignatura-docente");
    const selectSemestre = document.getElementById("asignatura-semestre");
    const selectMateria = document.getElementById("asignatura-materia");
    const cerrarModalAsignatura = document.getElementById("cerrar-modal-asignatura");
    const cancelarAsignatura = document.getElementById("cancelar-asignatura");
    const guardarAsignatura = document.getElementById("guardar-asignatura");
    const abrirModalAsignatura = document.getElementById("abrir-modal-asignatura");

    const pestanas = document.querySelectorAll(".pestana-docente");

    let temporizadorBusqueda = null;
    let temporizadorBusquedaHU6 = null;
    let asignaturasDisponibles = [];
    let docentesHU6 = [];

    // =====================================================
    // NOTIFICACIONES Y FUNCIONES GENERALES
    // =====================================================

    function notificar(mensaje, tipo = "info") {
        if (
            window.AulaSynModal &&
            typeof window.AulaSynModal.notificar === "function"
        ) {
            window.AulaSynModal.notificar(mensaje, tipo);
        } else {
            console.log(mensaje);
        }
    }

    async function confirmar(mensaje) {
        if (
            window.AulaSynModal &&
            typeof window.AulaSynModal.confirmar === "function"
        ) {
            return await window.AulaSynModal.confirmar(mensaje);
        }

        return false;
    }

    function escaparHTML(valor) {
        return String(valor ?? "").replace(/[&<>"']/g, caracter => {
            const caracteres = {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            };

            return caracteres[caracter];
        });
    }

    async function consultarAPI(url, opciones = {}) {
        const respuesta = await fetch(url, {
            credentials: "same-origin",
            ...opciones,
            headers: {
                ...(opciones.headers || {}),
                ...(opciones.body ? {
                    "Content-Type": "application/json"
                } : {})
            }
        });

        let resultado;

        try {
            resultado = await respuesta.json();
        } catch {
            throw new Error(
                "El servidor no devolvió una respuesta válida. " +
                "Verifica tu sesión e inténtalo nuevamente."
            );
        }

        if (!respuesta.ok) {
            throw new Error(
                resultado.mensaje ||
                "Ocurrió un error al realizar la solicitud."
            );
        }

        return resultado;
    }

    function mostrarModal(elemento) {
        if (!elemento) return;

        elemento.classList.add("visible");
        elemento.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
    }

    function ocultarModal(elemento) {
        if (!elemento) return;

        elemento.classList.remove("visible");
        elemento.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
    }

    // =====================================================
    // HU5: CARGAR DATOS INICIALES
    // =====================================================

    async function cargarDatosIniciales() {
        try {
            const datos = await consultarAPI(
                "/api/docentes/datos-iniciales"
            );

            llenarDocentes(datos.docentes || []);
            llenarSedes(datos.sedes || []);
            llenarFranjas(datos.franjas || []);

            asignaturasDisponibles = datos.asignaturas || [];

            llenarAsignaturas(asignaturasDisponibles);
            llenarDocentesSelectHU6();

        } catch (error) {
            console.error("Error al cargar datos iniciales:", error);
            notificar(error.message, "error");
        }
    }

    function llenarDocentes(docentes) {
        if (!selectDocente) return;

        selectDocente.innerHTML =
            '<option value="">Selecciona un docente</option>';

        docentes.forEach(docente => {
            const opcion = document.createElement("option");

            opcion.value = docente.id_usuario;
            opcion.textContent =
                `${docente.nombres} ${docente.apellidos}`;

            selectDocente.appendChild(opcion);
        });
    }

    function llenarSedes(sedes) {
        if (!selectSede || !filtroSede) return;

        selectSede.innerHTML =
            '<option value="">Selecciona una sede</option>';

        filtroSede.innerHTML =
            '<option value="">Todas las sedes</option>';

        sedes.forEach(sede => {
            const opcionFormulario = document.createElement("option");

            opcionFormulario.value = sede.id_sede;
            opcionFormulario.textContent = sede.nombre;

            selectSede.appendChild(opcionFormulario);

            const opcionFiltro = document.createElement("option");

            opcionFiltro.value = sede.id_sede;
            opcionFiltro.textContent = sede.nombre;

            filtroSede.appendChild(opcionFiltro);
        });
    }

    function llenarFranjas(franjas) {
        if (!selectFranja) return;

        selectFranja.innerHTML =
            '<option value="">Selecciona una franja</option>';

        franjas.forEach(franja => {
            const opcion = document.createElement("option");

            opcion.value = franja.id_franja;
            opcion.textContent =
                `${franja.nombre} - ${franja.hora_inicio} a ${franja.hora_fin}`;

            selectFranja.appendChild(opcion);
        });
    }

    function llenarAsignaturas(asignaturas) {
        if (!selectAsignatura) return;

        selectAsignatura.innerHTML =
            '<option value="">Sin asignatura específica</option>';

        asignaturas.forEach(asignatura => {
            const opcion = document.createElement("option");

            opcion.value = asignatura.id_asignatura;
            opcion.textContent = asignatura.nombre;

            selectAsignatura.appendChild(opcion);
        });
    }

    // =====================================================
    // HU5: CONSULTAR Y MOSTRAR DISPONIBILIDADES
    // =====================================================

    function mostrarCargando() {
        if (!tablaDisponibilidad) return;

        tablaDisponibilidad.innerHTML = `
            <tr>
                <td colspan="7" class="mensaje-tabla">
                    Cargando disponibilidades...
                </td>
            </tr>
        `;
    }

    async function cargarDisponibilidades() {
        if (!tablaDisponibilidad) return;

        mostrarCargando();

        const parametros = new URLSearchParams();

        const docente = buscarDocente
            ? buscarDocente.value.trim()
            : "";

        const sede = filtroSede ? filtroSede.value : "";
        const dia = filtroDia ? filtroDia.value : "";

        if (docente) parametros.append("docente", docente);
        if (sede) parametros.append("sede", sede);
        if (dia) parametros.append("dia", dia);

        const url = parametros.toString()
            ? `/api/docentes/disponibilidades?${parametros.toString()}`
            : "/api/docentes/disponibilidades";

        try {
            const datos = await consultarAPI(url);

            mostrarDisponibilidades(
                datos.disponibilidades || []
            );

        } catch (error) {
            console.error("Error al consultar disponibilidades:", error);

            tablaDisponibilidad.innerHTML = `
                <tr>
                    <td colspan="7" class="mensaje-tabla">
                        No fue posible cargar las disponibilidades.
                    </td>
                </tr>
            `;

            notificar(error.message, "error");
        }
    }

    function mostrarDisponibilidades(disponibilidades) {
        if (!tablaDisponibilidad) return;

        if (!disponibilidades.length) {
            tablaDisponibilidad.innerHTML = `
                <tr>
                    <td colspan="7" class="mensaje-tabla">
                        No se encontraron disponibilidades registradas.
                    </td>
                </tr>
            `;

            return;
        }

        tablaDisponibilidad.innerHTML = disponibilidades.map(registro => {
            const activa = registro.disponible === true;

            const estado = activa ? "Activa" : "Inactiva";
            const claseEstado = activa ? "activa" : "inactiva";
            const accion = activa ? "Desactivar" : "Activar";

            return `
                <tr>
                    <td>${escaparHTML(registro.docente)}</td>

                    <td>${escaparHTML(registro.dia_semana)}</td>

                    <td>${escaparHTML(registro.sede)}</td>

                    <td>
                        ${escaparHTML(registro.franja)}
                        <span class="detalle-horario">
                            ${escaparHTML(registro.hora_inicio)}
                            -
                            ${escaparHTML(registro.hora_fin)}
                        </span>
                    </td>

                    <td>${escaparHTML(registro.asignatura)}</td>

                    <td>
                        <span class="estado-disponibilidad ${claseEstado}">
                            ${estado}
                        </span>
                    </td>

                    <td>
                        <button
                            type="button"
                            class="boton-estado"
                            data-id="${escaparHTML(registro.id_disponibilidad)}"
                            data-estado="${activa ? "true" : "false"}"
                        >
                            ${accion}
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    // =====================================================
    // HU5: MODAL Y REGISTRO DE DISPONIBILIDAD
    // =====================================================

    function abrirModalDisponibilidad() {
        if (formulario) formulario.reset();

        mostrarModal(modal);
    }

    function cerrarModalDisponibilidad() {
        ocultarModal(modal);
    }

    if (botonAbrirModal) {
        botonAbrirModal.addEventListener(
            "click",
            abrirModalDisponibilidad
        );
    }

    if (botonCerrarModal) {
        botonCerrarModal.addEventListener(
            "click",
            cerrarModalDisponibilidad
        );
    }

    if (botonCancelar) {
        botonCancelar.addEventListener(
            "click",
            cerrarModalDisponibilidad
        );
    }

    if (modal) {
        modal.addEventListener("click", evento => {
            if (evento.target === modal) {
                cerrarModalDisponibilidad();
            }
        });
    }

    if (formulario) {
        formulario.addEventListener("submit", async evento => {
            evento.preventDefault();

            const datos = {
                id_usuario: selectDocente.value,
                dia_semana: selectDia.value,
                id_sede: selectSede.value,
                id_franja: selectFranja.value,
                id_asignatura: selectAsignatura.value || null
            };

            if (
                !datos.id_usuario ||
                !datos.dia_semana ||
                !datos.id_sede ||
                !datos.id_franja
            ) {
                notificar(
                    "Completa los campos obligatorios.",
                    "warning"
                );

                return;
            }

            botonGuardar.disabled = true;
            botonGuardar.textContent = "Guardando...";

            try {
                const resultado = await consultarAPI(
                    "/api/docentes/disponibilidades",
                    {
                        method: "POST",
                        body: JSON.stringify(datos)
                    }
                );

                cerrarModalDisponibilidad();
                formulario.reset();

                notificar(
                    resultado.mensaje ||
                    "Disponibilidad registrada correctamente.",
                    "success"
                );

                await cargarDisponibilidades();

            } catch (error) {
                console.error(
                    "Error al registrar disponibilidad:",
                    error
                );

                notificar(error.message, "error");

            } finally {
                botonGuardar.disabled = false;
                botonGuardar.textContent = "Guardar disponibilidad";
            }
        });
    }

        // =====================================================
    // HU5: ACTIVAR Y DESACTIVAR DISPONIBILIDADES
    // =====================================================

    if (tablaDisponibilidad) {
        tablaDisponibilidad.addEventListener("click", async evento => {

            const boton = evento.target.closest(".boton-estado");

            if (!boton) return;

            const id = boton.dataset.id;
            const estadoActual = boton.dataset.estado === "true";
            const nuevoEstado = !estadoActual;

            const accion = nuevoEstado ? "activar" : "desactivar";

            const aceptado = await confirmar(
                `¿Estás seguro de que deseas ${accion} esta disponibilidad?`
            );

            if (!aceptado) return;

            boton.disabled = true;

            try {
                const resultado = await consultarAPI(
                    `/api/docentes/disponibilidades/${id}/estado`,
                    {
                        method: "PATCH",
                        body: JSON.stringify({
                            disponible: nuevoEstado
                        })
                    }
                );

                notificar(
                    resultado.mensaje ||
                    "El estado se actualizó correctamente.",
                    "success"
                );

                await cargarDisponibilidades();

            } catch (error) {
                console.error("Error al cambiar el estado:", error);

                notificar(error.message, "error");

                boton.disabled = false;
            }
        });
    }

    // =====================================================
    // HU5: FILTROS
    // =====================================================

    if (buscarDocente) {
        buscarDocente.addEventListener("input", () => {

            clearTimeout(temporizadorBusqueda);

            temporizadorBusqueda = setTimeout(() => {
                cargarDisponibilidades();
            }, 350);
        });
    }

    if (filtroSede) {
        filtroSede.addEventListener("change", cargarDisponibilidades);
    }

    if (filtroDia) {
        filtroDia.addEventListener("change", cargarDisponibilidades);
    }

    // =====================================================
    // HU6: CARGAR DOCENTES EN EL SELECTOR
    // =====================================================

    function llenarDocentesSelectHU6() {
        if (!selectDocenteAsignatura) return;

        const seleccionActual = selectDocenteAsignatura.value;

        selectDocenteAsignatura.innerHTML =
            '<option value="">Selecciona un docente</option>';

        docentesHU6.forEach(docente => {
            const opcion = document.createElement("option");

            opcion.value = docente.id_usuario;
            opcion.textContent =
                `${docente.nombres} ${docente.apellidos}`;

            selectDocenteAsignatura.appendChild(opcion);
        });

        if (seleccionActual) {
            selectDocenteAsignatura.value = seleccionActual;
        }
    }

    // =====================================================
    // HU6: CONSULTAR DOCENTES Y SUS ASIGNATURAS
    // =====================================================

    async function cargarDocentesHU6() {
        if (!tablaDocentesHU6 && !tablaAsignaciones) return;

        try {
            const datos = await consultarAPI("/api/docentes/hu6");

            docentesHU6 = datos.docentes || [];

            llenarDocentesSelectHU6();
            mostrarDocentesHU6();
            mostrarAsignacionesHU6();

        } catch (error) {
            console.error("Error al cargar docentes HU6:", error);

            if (tablaDocentesHU6) {
                tablaDocentesHU6.innerHTML = `
                    <tr>
                        <td colspan="6" class="mensaje-tabla">
                            No fue posible cargar los docentes.
                        </td>
                    </tr>
                `;
            }

            if (tablaAsignaciones) {
                tablaAsignaciones.innerHTML = `
                    <tr>
                        <td colspan="4" class="mensaje-tabla">
                            No fue posible cargar las asignaturas asociadas.
                        </td>
                    </tr>
                `;
            }

            notificar(error.message, "error");
        }
    }

    // =====================================================
    // HU6: MOSTRAR DOCENTES EN LA TABLA
    // =====================================================

    function mostrarDocentesHU6() {
        if (!tablaDocentesHU6) return;

        const texto = buscarDocenteHU6
            ? buscarDocenteHU6.value.trim().toLowerCase()
            : "";

        const filtrados = docentesHU6.filter(docente => {

            const nombre =
                `${docente.nombres || ""} ${docente.apellidos || ""}`
                    .toLowerCase();

            const correo = String(docente.correo || "").toLowerCase();

            const documento =
                String(docente.documento || "").toLowerCase();

            return (
                nombre.includes(texto) ||
                correo.includes(texto) ||
                documento.includes(texto)
            );
        });

        if (!filtrados.length) {
            tablaDocentesHU6.innerHTML = `
                <tr>
                    <td colspan="6" class="mensaje-tabla">
                        No se encontraron docentes.
                    </td>
                </tr>
            `;

            return;
        }

        tablaDocentesHU6.innerHTML = filtrados.map(docente => {

            const asignaturas = docente.asignaturas || [];

            const estado = docente.estado_cuenta ||
                (docente.activo ? "Activo" : "Inactivo");

            return `
                <tr>
                    <td>
                        ${escaparHTML(
                            `${docente.nombres} ${docente.apellidos}`
                        )}
                    </td>

                    <td>${escaparHTML(docente.correo)}</td>

                    <td>${escaparHTML(docente.documento)}</td>

                    <td>${asignaturas.length}</td>

                    <td>${escaparHTML(estado)}</td>

                    <td>
                        <button
                            type="button"
                            class="boton-accion-docente"
                            data-accion="editar"
                            data-id="${escaparHTML(docente.id_usuario)}"
                        >
                            Editar
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    // =====================================================
    // HU6: MOSTRAR ASIGNATURAS ASOCIADAS
    // =====================================================

    function mostrarAsignacionesHU6() {
        if (!tablaAsignaciones) return;

        const filas = [];

        docentesHU6.forEach(docente => {

            (docente.asignaturas || []).forEach(asignatura => {

                filas.push(`
                    <tr>
                        <td>
                            ${escaparHTML(
                                `${docente.nombres} ${docente.apellidos}`
                            )}
                        </td>

                        <td>${escaparHTML(asignatura.nombre)}</td>

                        <td>${escaparHTML(asignatura.semestre)}</td>

                        <td>
                            <button
                                type="button"
                                class="boton-retirar-asignatura"
                                data-id-asociacion="${escaparHTML(
                                    asignatura.id_docente_asignatura
                                )}"
                            >
                                Retirar
                            </button>
                        </td>
                    </tr>
                `);
            });
        });

        tablaAsignaciones.innerHTML = filas.length
            ? filas.join("")
            : `
                <tr>
                    <td colspan="4" class="mensaje-tabla">
                        No hay asignaturas asociadas a docentes.
                    </td>
                </tr>
            `;
    }

    // =====================================================
    // HU6: BUSCAR DOCENTES
    // =====================================================

    if (buscarDocenteHU6) {
        buscarDocenteHU6.addEventListener("input", () => {

            clearTimeout(temporizadorBusquedaHU6);

            temporizadorBusquedaHU6 = setTimeout(() => {
                mostrarDocentesHU6();
            }, 250);
        });
    }

    // =====================================================
    // HU6: ABRIR MODAL PARA EDITAR DOCENTE
    // =====================================================

    function abrirEdicionDocente(id) {

        const docente = docentesHU6.find(
            item => String(item.id_usuario) === String(id)
        );

        if (!docente) {
            notificar(
                "No se encontró la información del docente.",
                "error"
            );

            return;
        }

        editarIdDocente.value = docente.id_usuario;
        editarNombres.value = docente.nombres || "";
        editarApellidos.value = docente.apellidos || "";
        editarCorreo.value = docente.correo || "";
        editarDocumento.value = docente.documento || "";

        mostrarModal(modalEditar);
    }

    function cerrarEdicionDocente() {
        ocultarModal(modalEditar);
    }

    if (tablaDocentesHU6) {
        tablaDocentesHU6.addEventListener("click", evento => {

            const boton = evento.target.closest(
                '[data-accion="editar"]'
            );

            if (!boton) return;

            abrirEdicionDocente(boton.dataset.id);
        });
    }

    if (cerrarModalEditar) {
        cerrarModalEditar.addEventListener(
            "click",
            cerrarEdicionDocente
        );
    }

    if (cancelarEditar) {
        cancelarEditar.addEventListener(
            "click",
            cerrarEdicionDocente
        );
    }

    if (modalEditar) {
        modalEditar.addEventListener("click", evento => {

            if (evento.target === modalEditar) {
                cerrarEdicionDocente();
            }
        });
    }

    // =====================================================
    // HU6: GUARDAR CAMBIOS DEL DOCENTE
    // =====================================================

    if (formularioEditar) {
        formularioEditar.addEventListener("submit", async evento => {

            evento.preventDefault();

            const id = editarIdDocente.value;

            const datos = {
                nombres: editarNombres.value.trim(),
                apellidos: editarApellidos.value.trim(),
                correo: editarCorreo.value.trim(),
                documento: editarDocumento.value.trim()
            };

            if (
                !id ||
                !datos.nombres ||
                !datos.apellidos ||
                !datos.correo ||
                !datos.documento
            ) {
                notificar("Completa todos los campos.", "warning");
                return;
            }

            guardarEditar.disabled = true;
            guardarEditar.textContent = "Guardando...";

            try {
                const resultado = await consultarAPI(
                    `/api/docentes/${id}`,
                    {
                        method: "PUT",
                        body: JSON.stringify(datos)
                    }
                );

                cerrarEdicionDocente();

                notificar(
                    resultado.mensaje ||
                    "Datos del docente actualizados correctamente.",
                    "success"
                );

                await cargarDocentesHU6();

            } catch (error) {
                console.error("Error al editar docente:", error);
                notificar(error.message, "error");

            } finally {
                guardarEditar.disabled = false;
                guardarEditar.textContent = "Guardar cambios";
            }
        });
    }

        // =====================================================
    // HU6: ACTUALIZAR ASIGNATURAS SEGÚN EL SEMESTRE
    // =====================================================

    function actualizarAsignaturasPorSemestre() {

        if (!selectMateria || !selectSemestre) return;

        const semestre = Number(selectSemestre.value);

        selectMateria.innerHTML =
            '<option value="">Selecciona una asignatura</option>';

        if (!semestre) return;

        const disponibles = asignaturasDisponibles.filter(
            asignatura => Number(asignatura.semestre) === semestre
        );

        disponibles.forEach(asignatura => {

            const opcion = document.createElement("option");

            opcion.value = asignatura.id_asignatura;
            opcion.textContent = asignatura.nombre;

            selectMateria.appendChild(opcion);
        });

        if (!disponibles.length) {
            selectMateria.innerHTML =
                '<option value="">No hay asignaturas para este semestre</option>';
        }
    }

    // =====================================================
    // HU6: ABRIR Y CERRAR MODAL DE ASIGNATURAS
    // =====================================================

    function abrirAsociarAsignatura() {

        if (formularioAsignatura) {
            formularioAsignatura.reset();
        }

        actualizarAsignaturasPorSemestre();
        llenarDocentesSelectHU6();

        mostrarModal(modalAsignatura);
    }

    function cerrarAsociarAsignatura() {
        ocultarModal(modalAsignatura);
    }

    if (abrirModalAsignatura) {
        abrirModalAsignatura.addEventListener(
            "click",
            abrirAsociarAsignatura
        );
    }

    if (cerrarModalAsignatura) {
        cerrarModalAsignatura.addEventListener(
            "click",
            cerrarAsociarAsignatura
        );
    }

    if (cancelarAsignatura) {
        cancelarAsignatura.addEventListener(
            "click",
            cerrarAsociarAsignatura
        );
    }

    if (modalAsignatura) {
        modalAsignatura.addEventListener("click", evento => {

            if (evento.target === modalAsignatura) {
                cerrarAsociarAsignatura();
            }
        });
    }

    if (selectSemestre) {
        selectSemestre.addEventListener(
            "change",
            actualizarAsignaturasPorSemestre
        );
    }

    // =====================================================
    // HU6: ASOCIAR ASIGNATURA A UN DOCENTE
    // =====================================================

    if (formularioAsignatura) {
        formularioAsignatura.addEventListener("submit", async evento => {

            evento.preventDefault();

            const idDocente = selectDocenteAsignatura.value;
            const idAsignatura = selectMateria.value;

            if (!idDocente || !idAsignatura) {
                notificar(
                    "Selecciona un docente, un semestre y una asignatura.",
                    "warning"
                );

                return;
            }

            guardarAsignatura.disabled = true;
            guardarAsignatura.textContent = "Guardando...";

            try {
                const resultado = await consultarAPI(
                    `/api/docentes/${idDocente}/asignaturas`,
                    {
                        method: "POST",
                        body: JSON.stringify({
                            id_asignatura: idAsignatura
                        })
                    }
                );

                cerrarAsociarAsignatura();

                notificar(
                    resultado.mensaje ||
                    "Asignatura asociada correctamente.",
                    "success"
                );

                await cargarDocentesHU6();

            } catch (error) {
                console.error("Error al asociar asignatura:", error);

                notificar(error.message, "error");

            } finally {
                guardarAsignatura.disabled = false;
                guardarAsignatura.textContent = "Asociar asignatura";
            }
        });
    }

    // =====================================================
    // HU6: RETIRAR ASIGNATURA DE UN DOCENTE
    // =====================================================

    if (tablaAsignaciones) {
        tablaAsignaciones.addEventListener("click", async evento => {

            const boton = evento.target.closest(
                ".boton-retirar-asignatura"
            );

            if (!boton) return;

            const id = boton.dataset.idAsociacion;

            const aceptado = await confirmar(
                "¿Estás seguro de que deseas retirar esta asignatura del docente?"
            );

            if (!aceptado) return;

            boton.disabled = true;

            try {
                const resultado = await consultarAPI(
                    `/api/docentes/asociaciones/${id}`,
                    {
                        method: "DELETE"
                    }
                );

                notificar(
                    resultado.mensaje ||
                    "Asociación retirada correctamente.",
                    "success"
                );

                await cargarDocentesHU6();

            } catch (error) {
                console.error("Error al retirar asociación:", error);

                notificar(error.message, "error");

                boton.disabled = false;
            }
        });
    }

    // =====================================================
    // CAMBIAR ENTRE PESTAÑAS
    // =====================================================

    pestanas.forEach(pestana => {

        pestana.addEventListener("click", () => {

            const destino = pestana.dataset.pestana;

            pestanas.forEach(item => {
                item.classList.remove("activa");
            });

            document.querySelectorAll(".contenido-pestana").forEach(
                contenido => {
                    contenido.classList.remove("activa");
                }
            );

            pestana.classList.add("activa");

            const contenidoDestino = document.getElementById(
                `contenido-${destino}`
            );

            if (contenidoDestino) {
                contenidoDestino.classList.add("activa");
            }

            if (destino === "asignaturas") {
                cargarDocentesHU6();
            }
        });
    });

    // =====================================================
    // CERRAR MODALES CON LA TECLA ESCAPE
    // =====================================================

    document.addEventListener("keydown", evento => {

        if (evento.key !== "Escape") return;

        [modal, modalEditar, modalAsignatura].forEach(elemento => {

            if (
                elemento &&
                elemento.classList.contains("visible")
            ) {
                ocultarModal(elemento);
            }
        });
    });

    // =====================================================
    // INICIAR MÓDULO
    // =====================================================

    async function iniciarModulo() {

        await cargarDatosIniciales();

        await cargarDisponibilidades();

        await cargarDocentesHU6();
    }

    iniciarModulo();

});
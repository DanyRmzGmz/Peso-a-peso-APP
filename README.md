# Peso a Peso - Gestor de Gastos y Finanzas Personales

![Python Version](https://img.shields.io/badge/Python-3.13-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Flet UI](https://img.shields.io/badge/UI%20Framework-Flet%20%2F%20Flutter-orange.svg?style=for-the-badge&logo=flutter&logoColor=white)
![Database](https://img.shields.io/badge/Database-SQLite3-lightgrey.svg?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-red.svg?style=for-the-badge)

## 1. Introducción
``
**Peso a Peso** es un ecosistema de escritorio robusto y multiplataforma diseñado para la auditoría, control, proyección y optimización financiera individual. Construido sobre la base de **Python 3.13** y la potencia reactiva de **Flet** (motorizado por Flutter de forma nativa), el sistema ofrece una interfaz moderna de tres paneles concurrentes, mitigando las latencias de renderizado tradicionales en aplicaciones financieras complejas.

El software resuelve de forma nativa la desconexión imperante entre el flujo de efectivo líquido diario, el uso de instrumentos de crédito revolventes complejos y las obligaciones pasivas a largo plazo (préstamos con amortizaciones indexadas). A través de un motor de persistencia relacional puramente local basado en **SQLite3**, la aplicación garantiza la soberanía absoluta de los datos sensibles del usuario sin depender de microservicios en la nube u orquestadores propensos a brechas de seguridad perimetral.

---

## 2. Licenciamiento Dual y Modelo Comercial

Este repositorio de código abierto se distribuye estrictamente bajo los términos y directrices de la **Licencia PolyForm Noncommercial 1.0.0**.

### Esquema de Permisos y Restricciones Legales
* **Uso Permitido:** Se autoriza de forma gratuita el uso, copia, modificación y distribución interna de este software exclusivamente para fines personales, académicos, de auto-aprendizaje, investigación científica y auditorías técnicas privadas de código fuente.
* **Restricciones Comerciales Explícitas:** Queda estrictamente prohibida la explotación comercial de este software, su distribución con fines de lucro directo o indirecto, su reventa, empaquetado integrado dentro de soluciones propietarias corporativas o su utilización para actividades de consultoría financiera comercial remunerada por parte de terceros.

### Propiedad Intelectual y Retención de Derechos
El Copyright íntegro de la arquitectura lógica, el diseño de la base de datos y la identidad visual de la interfaz de usuario pertenece de manera exclusiva al autor original del proyecto. El creador se reserva el derecho exclusivo e inalienable de comercializar variantes avanzadas del software bajo un modelo SaaS o licencias comerciales tradicionales, incluyendo el futuro lanzamiento global de **Peso a Peso Plus**, el cual integrará conciliación bancaria automatizada y sincronización multifactorial en la nube.

---

## 3. Arquitectura y Motores Internos

La estabilidad transaccional de **Peso a Peso** descansa sobre módulos de ingeniería lógica de software desacoplados que operan en paralelo de forma síncrona:

### Motor de Eslabones Encadenados (Chained State Machine)
El núcleo de la gestión de transacciones recurrentes no se basa en simples temporizadores (cron-jobs) volátiles, sino en una **Máquina de Estados Finos e Idempotente** implementada directamente en el motor relacional mediante banderas jerárquicas discretas:
* **Estado 0 (Inactivo / Transacción Pura):** Registros históricos tradicionales de ingresos y gastos que afectan la liquidez real de forma estática.
* **Estado 1 (Puntero Vivo / Proyección Futura):** Una plantilla transaccional flotante proyectada cronológicamente en el futuro. Funciona como un marcador de posición que representa la siguiente fecha de vencimiento de un compromiso recurrente (ej. suscripciones, rentas, nóminas).
* **Estado 2 (Procesado Histórico Recurrente):** Cuando la fecha del sistema alcanza o supera la fecha del Puntero Vivo (date <= today), el motor ejecuta una mutación síncrona. El puntero actual se congela en Estado 2 para integrarse formalmente al balance del historial visible, y de manera inmediata e idempotente calcula el delta cronológico preciso (semanal, quincenal, mensual, bimensual, trimestral, semestral o anual) para insertar el nuevo Puntero Vivo de Estado 1 en la base de datos. Este proceso de encadenamiento se repite recursivamente garantizando que jamás existan descuadres ni duplicidades transaccionales ante apagados inesperados de la aplicación.

### Blindaje de Balances y Mitigación de Duplicados en Tarjetas de Crédito
El cálculo de liquidez neta unificada utiliza subconsultas complejas aisladas que previenen el error clásico de doble contabilidad al interactuar con pasivos financieros de tarjetas de crédito. Los traspasos y pagos destinados a mitigar deudas acumuladas en plásticos revolventes se registran a través de la entidad abstracta de transferencias (`transfers`), inyectando de forma síncrona un reflejo histórico visual en la tabla de transacciones de la tarjeta afectada, pero filtrando de manera explícita estos identificadores transaccionales dentro del cálculo general de balance global del mes. Esto asegura que el pago de un servicio con tarjeta de crédito afecte el balance operativo en el instante de su consumo, y que la posterior liquidación en efectivo de dicha tarjeta no altere artificialmente el balance operativo general del usuario.

### Motor de Pasivos y Amortización Indexada
La tabla de préstamos (`loans`) opera de forma simbiótica con el libro mayor transaccional. Al dar de alta un pasivo fijo (v.g., créditos automotrices o hipotecarios), el sistema aplica el algoritmo de interés simple sobre el saldo base inicial configurado:

Total con Interés = Monto Base + (Monto Base * (Tasa de Interés / 100))

Cada abono inyectado desde una cuenta origen hacia el ID de un préstamo a través de la interfaz de transferencias disminuye matemáticamente la propiedad de remanente (`remaining`) e incrementa el porcentaje real de progreso de forma dinámica. El borrado o remoción de préstamos ejecuta un disparador de desvinculación segura en cascada (Nullify Target Constraint), preservando el registro histórico del dinero que salió de las cuentas de origen pero liberando al esquema relacional de dependencias rotas.

### Seguridad Híbrida Criptográfica de Dos Vías
La salvaguarda de la integridad perimetral de la aplicación se ejecuta localmente mediante dos componentes independientes inyectados en la tabla `app_settings`:
1. **Mecanismo de Autenticación Local:** El PIN numérico seleccionado por el usuario es sometido a un algoritmo de dispersión criptográfica de una vía **SHA-256**. El software carece de mecanismos de recuperación basados en texto plano; el acceso al panel principal está condicionado a la coincidencia exacta de los hashes resultantes en memoria volátil.
2. **Factor de Autenticación Dual (2FA TOTP):** Utiliza la especificación criptográfica **RFC 6238**. El sistema genera localmente una clave secreta pseudoaleatoria codificada en Base32, la cual genera dinámicamente un código QR para su vinculación con aplicaciones externas como Google Authenticator o Bitwarden. Durante el ciclo de vida del login, el software valida síncronamente el código temporal TOTP introducido por el usuario contra las ventanas de tiempo del algoritmo interno de paso de tiempo, neutralizando vectores de ataque de acceso físico no autorizado.

---

## 4. Galería Visual de la Aplicación

La documentación técnica del sistema se encuentra completamente respaldada por los siguientes registros visuales reales extraídos directamente de la interfaz operativa del programa, almacenados localmente en la carpeta `screenshots/`.

### Bloque 1: Arranque, Autenticación y Seguridad

| Artefacto Visual | Descripción de Interfaz de Usuario y Lógica Operativa | Renderizado de Captura real en GitHub |
| :--- | :--- | :--- |
| **Autenticación 1** | **Pantalla de bloqueo de seguridad principal**. Formulario centrado y minimalista para la validación obligatoria del NIP maestro SHA-256 con opción de visibilidad oculta. | ![Autenticación 1](screenshots/Autenticación%201.png) |
| **Autenticación 2** | **Ventana de Recuperación de Acceso de Doble Factor (2FA)**. Entrada de validación para el código OTP síncrono de 6 dígitos generado de forma externa. | ![Autenticación 2](screenshots/Autenticación%202.png) |
| **Configuración 3** | **Modal de Asignación y Cambio de NIP**. Entrada enmascarada doble para inyectar o actualizar las credenciales numéricas locales de forma aislada. | ![Configuración 3](screenshots/Configuración%203.png) |
| **Configuración 4** | **Setup del Segundo Factor de Autenticación (2FA)**. Despliegue dinámico del código QR codificado y la llave Base32 secreta para emparejamiento con Google Authenticator. | ![Configuración 4](screenshots/Configuración%204.png) |

### Bloque 2: Dashboard General de Control

| Artefacto Visual | Descripción de Interfaz de Usuario y Lógica Operativa | Renderizado de Captura real en GitHub |
| :--- | :--- | :--- |
| **General 1** | **Resumen mensual unificado (KPIs)**. Despliegue de tarjetas de saldo del periodo, saldos arrastrados, desglose de liquidez por medio de pago (Efectivo/Bancos) y el gráfico analítico Matplotlib de tendencias de ingresos vs gastos diarios. | ![General 1](screenshots/General%201.png) |
| **General 2** | **Vista extendida inferior del Dashboard**. Tabla interactiva con el registro cronológico descendente de los últimos movimientos operados en el mes en curso. | ![General 2](screenshots/General%202.png) |

### Bloque 3: Gestión Operativa de Flujos (Gastos e Ingresos)

| Artefacto Visual | Descripción de Interfaz de Usuario y Lógica Operativa | Renderizado de Captura real en GitHub |
| :--- | :--- | :--- |
| **Gastos 1** | **Módulo de egresos y cargas recurrentes**. Formulario emergente integrado sobre el grid de categorías para dar de alta consumos, con interruptor de recurrencia y selector de frecuencias periódicas. | ![Gastos 1](screenshots/Gastos%201.png) |
| **Ingresos 1** | **Módulo de entradas variables y fijas**. Formulario parametrizado para registrar flujos de efectivo positivos, categorización rápida de favoritos e inyección idempotente al motor de eslabones. | ![Ingresos 1](screenshots/Ingresos%201.png) |

### Bloque 4: Panel de Pasivos, Créditos y Amortizaciones

| Artefacto Visual | Descripción de Interfaz de Usuario y Lógica Operativa | Renderizado de Captura real en GitHub |
| :--- | :--- | :--- |
| **Deuda 1** | **Sección maestra de cuentas y registro de préstamos**. Vista unificada de líneas de crédito revolventes activas y formulario para indexar pasivos a plazos fijos con tasa de interés. | ![Deuda 1](screenshots/Deuda%201.png) |
| **Deuda 2** | **Formulario de mitigación y abono a préstamos**. Modal para inyectar amortizaciones líquidas directas desde un método de pago origen hacia el saldo insoluto del crédito seleccionado. | ![Deuda 2](screenshots/Deuda%202.png) |
| **Deuda 3** | **Flujo de liquidación de Tarjetas de Crédito**. Modal adaptativo con cálculo automatizado para cubrir el pago total para no generar intereses en base al corte del plástico. | ![Deuda 3](screenshots/Deuda%203.png) |
| **Deuda 4** | **Orquestador de Transferencias Propias Interbancarias**. Interfaz síncrona para mover flujos de capital entre cuentas de débito y ahorro sin alterar el balance de gastos netos. | ![Deuda 4](screenshots/Deuda%204.png) |
| **Deuda 5** | **Desglose granular de consumos revolventes**. Subpanel interactivo que lista de manera cronológica cada cargo individual y suscripción asociada al plástico seleccionado. | ![Deuda 5](screenshots/Deuda%205.png) |

### Bloque 5: Auditoría Avanzada e Históricos

| Artefacto Visual | Descripción de Interfaz de Usuario y Lógica Operativa | Renderizado de Captura real en GitHub |
| :--- | :--- | :--- |
| **Historial 1** | **Módulo de consulta macro y filtros avanzados**. Filtros dinámicos por mes, año o cuenta específica, acompañados de gráficos de series temporales completos y tabla de acciones. | ![Historial 1](screenshots/Historial%201.png) |
| **Historial 2** | **Gráfico analítico de dona de egresos**. Representación porcentual interactiva de los rubros operativos y gastos hormiga (Renta, Despensa, Internet) del periodo consultado. | ![Historial 2](screenshots/Historial%202.png) |
| **Historial 3** | **Análisis anual e histórico consolidado**. Histograma de barras cruzadas que evalúa el balance de flujo neto mensual histórico acumulado a lo largo del año. | ![Historial 3](screenshots/Historial%203.png) |
| **Historial 4** | **Auditoría macro global de egresos distribuidos**. Segmentación de la dona analítica expandida en el modo de vista histórica unificada de todas las cuentas del sistema. | ![Historial 4](screenshots/Historial%204.png) |
| **Historial 5** | **Aislamiento de flujos en tabla histórica**. Vista filtrada pura de la contabilidad de ingresos verificados antes de ejecutar procesos de exportación de reportes hacia el disco. | ![Historial 5](screenshots/Historial%205.png) |
| **Historial CSV** | **Reporte físico generado y estructurado**. Demostración técnica del archivo de salida `.csv` abierto en una suite de hojas de cálculo, validando la integridad del esquema relacional y las columnas de datos. | ![Historial CSV](screenshots/Historial%20CSV.png) |

### Bloque 6: Ajustes y Salvaguarda de Persistencia

| Artefacto Visual | Descripción de Interfaz de Usuario y Lógica Operativa | Renderizado de Captura real en GitHub |
| :--- | :--- | :--- |
| **Configuración 1** | **Panel general de control de variables**. Configuración de preferencias regionales, idioma, moneda, asignación de rutas locales de reportes e interruptores de seguridad perimetral. | ![Configuración 1](screenshots/Configuración%201.png) |
| **Configuración 2** | **Asistente de inicialización de cuentas de fábrica**. Formulario de inyección para estructurar los parámetros iniciales de operación de tarjetas de crédito o débitos nuevos. | ![Configuración 2](screenshots/Configuración%202.png) |
| **Configuración 5** | **Explorador y selector nativo de restauración**. Ventana del sistema operativo integrada para cargar copias físicas en caliente (`.db`) con rollback automatizado ante archivos corruptos. | ![Configuración 5](screenshots/Configuración%205.png) |
| **Configuración 6** | **Disparador preventivo de la Zona de Peligro**. Ventana de advertencia modal con doble confirmación restrictiva ante la orden de borrado completo y purga física del sistema. | ![Configuración 6](screenshots/Configuración%206.png) |

### Bloque 7: Internacionalización y Localización (English Interface)

| Artefacto Visual | Descripción de Interfaz de Usuario y Lógica Operativa | Renderizado de Captura real en GitHub |
| :--- | :--- | :--- |
| **English 1** | **Main Dashboard Localization**. Despliegue completo del panel general adaptado al idioma Inglés para el usuario "Verso". Muestra la traducción estricta de KPIs (*Dragged Balance*, *Period Balance*, *Available Credit*) y la reestructuración del gráfico de tendencias diarias. | ![English 1](screenshots/English%201.png) |
| **English 2** | **Expenses Engine Localization**. Panel de control operativo de egresos reflejando la internacionalización atómica de categorías fijas (*Mortgage*, *Rent*, *Water*, *Gas*) y la traducción completa de la matriz de estados del motor de recurrencias (*Daily*, *Weekly*, *Biweekly*, *Monthly*, *Bimonthly*, *Quarterly*, *Semi-annually*, *Yearly*). | ![English 2](screenshots/English%202.png) |
| **English 3** | **Income Module Localization**. Formulario reactivo de inyección de capital ("Register Dividends") y traducción del entorno relacional para flujos pasivos y extraordinarios (*Property Rental*, *Investments*, *Interests*). | ![English 3](screenshots/English%203.png) |
| **English 4** | **Debts & Credit Panel Localization**. Interfaz de pasivos unificada en inglés que despliega el asistente de enrutamiento de flujos internos (*Own Transfer*) con los campos lógicos sanitizados (*Where is the money coming from? / Where is the money going to?*). | ![English 4](screenshots/English%204.png) |
| **English 5** | **Advanced History Audit Localization**. Módulo de consulta macro e historial transaccional bilingüe. Traduce dinámicamente las leyendas del gráfico analítico de dona (*Debt payment*, *Groceries*, *Gym*) y las columnas de la tabla de auditoría física. | ![English 5](screenshots/English%205.png) |
| **English 6** | **Settings & Hazard Warning Localization**. Panel general de ajustes con tipografía adaptada, mostrando la llamada síncrona del modal crítico de purga de persistencia en la zona de peligro (*¡Irreversible Action! Are you sure you want to delete all history?*). | ![English 6](screenshots/English%206.png) |

---

## 5. Instalación y Requisitos

Para desplegar el entorno de desarrollo local de **Peso a Peso**, asegúrese de contar con **Python 3.13** instalado en su sistema operativo. Siga de forma meticulosa la siguiente secuencia de comandos en su consola:

```bash
# 1. Clonar el repositorio oficial de forma local desde el servidor de GitHub
git clone [https://github.com/usuario/pesoapeso.git](https://github.com/usuario/pesoapeso.git)
cd pesoapeso

# 2. Construir un entorno virtual aislado de desarrollo (Venv) para contener dependencias
python -m venv venv

# 3. Ejecutar la activación del entorno virtual de acuerdo con la arquitectura de su sistema operativo
# En sistemas basados en Unix (Linux / macOS):
source venv/bin/activate
# En sistemas basados en Windows (Command Prompt / PowerShell):
venv\Scripts\activate

# 4. Actualizar el gestor de paquetes pip e instalar las dependencias críticas del núcleo
pip install --upgrade pip
pip install flet matplotlib python-dateutil pyotp qrcode Pillow

# 5. Iniciar la ejecución síncrona de la aplicación en modo de desarrollo local
python main.py

# 6. Compilación de Producción Seguro (Anti-Virus)
El empaquetado de aplicaciones desarrolladas bajo el ecosistema Python utilizando frameworks gráficos suele disparar alertas heurísticas erróneas (Falsos Positivos) en los motores de protección de Windows Defender u otros antivirus comerciales si se compilan bajo el parámetro de archivo único (--onefile). Esto ocurre debido a que la extracción dinámica de librerías dinámicas binarias (.DLL) en el directorio temporal AppData\Local\Temp\_MEIxxxxxx emula patrones de comportamiento comunes en troyanos descargadores.
Para garantizar la máxima transparencia en la distribución binaria y mitigar por completo este comportamiento, es un estándar técnico mandatorio compilar el software utilizando el modo de directorio distribuido (--onedir). Esto mantiene los archivos binarios expuestos y legibles para los escáneres perimetrales del sistema operativo, permitiendo que la carpeta resultante sea distribuida de manera segura empaquetada dentro de un contenedor comprimido estandarizado .ZIP.

Ejecute el siguiente comando estructurado de PyInstaller para generar el empaquetado formal de producción:
pyinstaller --clean \
            --onedir \
            --noconsole \
            --name="Peso_a_Peso" \
            --icon="assets/logo.ico" \
            --add-data="assets;assets" \
            --hidden-import="flet" \
            --hidden-import="matplotlib" \
            --hidden-import="dateutil" \
            --hidden-import="pyotp" \
            --hidden-import="qrcode" \
            --hidden-import="PIL" \
            main.pys

Directrices Post-Compilación
Una vez concluida con éxito la tarea de empaquetado del ejecutable:

La suite de empaquetado generará el artefacto binario final dentro del directorio raíz local ./dist/Peso_a_Peso/.

Verifique minuciosamente que la estructura de la carpeta assets/ (que almacena fuentes tipográficas, logotipos, archivos .png e íconos .ico del sistema) haya sido inyectada de forma transparente e íntegra junto al ejecutable maestro Peso_a_Peso.exe.

Proceda a comprimir el directorio completo ./dist/Peso_a_Peso/ en un archivo binario .ZIP para su distribución segura a los usuarios finales de su organización.

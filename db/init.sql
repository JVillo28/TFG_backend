-- =============================================================================
-- BioSim — inicializacion de base de datos
-- =============================================================================
-- Este script crea la base de datos, las tres tablas del proyecto
-- (users, admin, research) y carga el schema de simulacion vigente.
--
-- Se monta automaticamente en el contenedor MySQL como
--   /docker-entrypoint-initdb.d/init.sql
-- por lo que se ejecuta una unica vez, en el primer arranque.
--
-- Las tablas coinciden exactamente con los modelos SQLAlchemy
-- definidos en backend/app/models/. El backend sigue llamando a
-- Base.metadata.create_all() en el arranque, pero al existir ya las
-- tablas la llamada es idempotente.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS biosim
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE biosim;

-- -----------------------------------------------------------------------------
-- Tabla: users
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id          INT           NOT NULL AUTO_INCREMENT,
  name        VARCHAR(100)  NOT NULL,
  email       VARCHAR(255)  NOT NULL UNIQUE,
  created_at  DATETIME      NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME      NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Tabla: admin (patron singleton, id=1)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin (
  id           INT       NOT NULL,
  json_schema  JSON      NOT NULL,
  created_at   DATETIME  NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME  NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Tabla: research
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS research (
  id             INT                                       NOT NULL AUTO_INCREMENT,
  name           VARCHAR(100)                              NOT NULL DEFAULT 'NEW RESEARCH',
  research_json  JSON                                      NOT NULL,
  user_id        INT                                       NOT NULL,
  status         ENUM('draft','running','finished')        NULL DEFAULT 'draft',
  created_at     DATETIME                                  NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME                                  NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_research_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- -----------------------------------------------------------------------------
-- Datos iniciales
-- -----------------------------------------------------------------------------

-- Usuario por defecto (id=1). Sin autenticacion en esta version del TFG:
-- cualquier acceso desde el frontend usa este id como propietario de las
-- investigaciones que se creen.
INSERT INTO users (id, name, email) VALUES
  (1, 'Usuario demo', 'demo@biosim.local');

-- Schema de simulacion vigente: 8 secciones (Cells, Agents, Events, Feeder,
-- Alignment, Environment, Transporters, General Configuration).
INSERT INTO admin (id, json_schema) VALUES (1, '{"type":"object","title":"Simulation Configuration","required":["generalConfiguration","environment","cells","alignment","agents","transporters","feeder","events"],"properties":{"cells":{"type":"array","items":{"if":{"properties":{"form":{"const":"capsule"}}},"then":{"required":["height"]},"type":"object","required":["cellName","layerName","form","radius","color","number"],"properties":{"form":{"enum":["sphere","capsule"],"type":"string","title":"Form","description":"Shape of the cell"},"color":{"type":"string","title":"Color","pattern":"^#[0-9A-Fa-f]{6}$","description":"Display color of the cell in hex format"},"height":{"type":"number","title":"Height","minimum":0,"description":"Length of the straight section of the capsule"},"layers":{"type":"array","items":{},"title":"Layers","description":"Additional layers of the cell"},"number":{"type":"integer","title":"Number","minimum":1,"description":"Number of cells of this type in the simulation"},"radius":{"type":"number","title":"Radius","minimum":0,"description":"Radius of the cell (for sphere: full radius; for capsule: radius of the semicircular caps)"},"cellName":{"type":"string","title":"Cell Name","description":"Name identifier for the cell type"},"layerName":{"enum":["outer membrane"],"type":"string","title":"Layer Name","description":"Membrane layer of the cell"}}},"title":"Cells","description":"List of cell types present in the simulation"},"agents":{"type":"object","title":"Agents","required":["molecules"],"properties":{"molecules":{"type":"array","items":{"type":"object","required":["name","molecularWeight","radius","diffusionRate","color","number","maxLayer","minLayer","cellLocalization","layerLocalization","form"],"properties":{"form":{"enum":["sphere"],"type":"string","title":"Form","description":"Shape of the molecule"},"name":{"type":"string","title":"Name","description":"Name identifier for the molecule type"},"color":{"type":"string","title":"Color","pattern":"^#[0-9A-Fa-f]{6}$","description":"Display color of the molecule in hex format"},"number":{"type":"integer","title":"Number","minimum":0,"description":"Number of molecules of this type in the simulation"},"radius":{"type":"number","title":"Radius","minimum":0,"description":"Radius of the molecule"},"radInfl":{"type":"number","title":"Radius of Influence","description":"TODO: ask the teacher"},"maxLayer":{"enum":["exterior","outerMembrane","outerPeriplasm","peptidoglycan","innerPeriplasm","innerMembrane","cytoplasm"],"type":"string","title":"Max Layer","description":"Maximum layer the molecule can reach"},"minLayer":{"enum":["exterior","outerMembrane","outerPeriplasm","peptidoglycan","innerPeriplasm","innerMembrane","cytoplasm"],"type":"string","title":"Min Layer","description":"Minimum layer the molecule can reach"},"radInflWith":{"type":"string","title":"Radius of Influence With","description":"TODO: ask the teacher"},"diffusionRate":{"type":"object","title":"Diffusion Rate","required":["exterior","outerMembrane","outerPeriplasm","peptidoglycan","innerPeriplasm","innerMembrane","cytoplasm"],"properties":{"exterior":{"type":"number","title":"Exterior"},"cytoplasm":{"type":"number","title":"Cytoplasm"},"innerMembrane":{"type":"number","title":"Inner Membrane"},"outerMembrane":{"type":"number","title":"Outer Membrane"},"peptidoglycan":{"type":"number","title":"Peptidoglycan"},"innerPeriplasm":{"type":"number","title":"Inner Periplasm"},"outerPeriplasm":{"type":"number","title":"Outer Periplasm"}},"description":"Rate at which the molecule diffuses through each layer"},"molecularWeight":{"type":"number","title":"Molecular Weight","minimum":0,"description":"Molecular weight of the molecule"},"cellLocalization":{"enum":["exterior","outerMembrane","outerPeriplasm","peptidoglycan","innerPeriplasm","innerMembrane","cytoplasm"],"type":"string","title":"Cell Localization","description":"Layer where the molecule is localized relative to the cell"},"layerLocalization":{"enum":["exterior","outerMembrane","outerPeriplasm","peptidoglycan","innerPeriplasm","innerMembrane","cytoplasm"],"type":"string","title":"Layer Localization","description":"Specific layer where the molecule resides"}}},"title":"Molecules","description":"List of molecule types in the simulation"},"ribosomes":{"type":"array","items":{},"title":"Ribosomes","description":"List of ribosome types (not currently used)"}},"description":"Biological agents present in the simulation"},"events":{"type":"object","title":"Events","required":["kill"],"properties":{"kill":{"type":"array","items":{"type":"object","required":["killer","trigger","affected","threshold"],"properties":{"killer":{"type":"string","title":"Killer","description":"Object that causes the kill (cell name, molecule name, or ''boundingBox'' for simulation boundaries)"},"trigger":{"enum":["onRebound"],"type":"string","title":"Trigger","description":"Event that triggers the kill"},"affected":{"type":"string","title":"Affected","description":"Object that is destroyed (cell name or molecule name)"},"threshold":{"type":"integer","title":"Threshold","minimum":1,"description":"Number of collisions needed to trigger the kill"}}},"title":"Kill","description":"Kill events: define when a molecule is destroyed upon collision with another object"},"reaction":{"type":"array","items":{},"title":"Reaction","description":"Reaction events (not currently used)"},"transform":{"type":"array","items":{},"title":"Transform","description":"Transform events (not currently used)"}},"description":"Simulation events that define interactions between agents"},"feeder":{"type":"array","items":{"type":"object","required":["create","type","location","everyStep","productionNumber","maxConcentration"],"properties":{"type":{"enum":["secreted"],"type":"string","title":"Type","description":"Production method"},"create":{"type":"string","title":"Create","description":"Name of the molecule to be produced (must match a molecule name from agents)"},"location":{"type":"string","title":"Location","description":"Name of the cell that secretes the molecule (must match a cell name from cells)"},"everyStep":{"type":"integer","title":"Every Step","minimum":1,"description":"Frequency in simulation steps at which the molecule is produced"},"maxConcentration":{"type":"integer","title":"Max Concentration","minimum":0,"description":"Maximum number of molecules allowed; production stops if this limit is reached"},"productionNumber":{"type":"integer","title":"Production Number","minimum":1,"description":"Number of molecules produced each time"}}},"title":"Feeder","description":"Rules defining how molecules are produced (secreted) by cells during the simulation"},"alignment":{"if":{"properties":{"type":{"const":"RANDOM"}}},"else":{"required":["positions"]},"then":{"required":["maxPlacementAttempts","seed"]},"type":"object","title":"Alignment","required":["type"],"properties":{"seed":{"type":"integer","title":"Seed","description":"Seed for the random number generator. Use -1 for a random seed, or a specific value to reproduce the same placement"},"type":{"enum":["RANDOM","ALIGNMENT"],"type":"string","title":"Type","description":"Positioning method for cells"},"positions":{"type":"array","items":{"type":"string"},"title":"Positions","description":"Explicit cell positions (used with ALIGNMENT). Format: CellName_Index,x,y,z"},"maxPlacementAttempts":{"type":"integer","title":"Max Placement Attempts","minimum":1,"description":"Maximum number of attempts to place each cell without overlapping (used with RANDOM)"}},"description":"Cell positioning strategy within the environment"},"environment":{"type":"object","title":"Environment","required":["width","height","length"],"properties":{"width":{"type":"number","title":"Width","minimum":0,"description":"Width of the environment"},"height":{"type":"number","title":"Height","minimum":0,"description":"Height of the environment"},"length":{"type":"number","title":"Length","minimum":0,"description":"Length of the environment"}},"description":"Dimensions of the simulation environment"},"transporters":{"type":"array","items":{},"title":"Transporters","description":"List of transporter types (not currently used)"},"generalConfiguration":{"type":"object","title":"General Configuration","required":["totalTries","dirOutput","fileOutput","simulationName","simulationType"],"properties":{"dirOutput":{"type":"string","title":"Output Directory","description":"Directory path where simulation output will be saved"},"fileOutput":{"type":"string","title":"Output File","description":"Name of the output file"},"totalTries":{"type":"integer","title":"Total Tries","minimum":1,"description":"Maximum tries for putting a body into the environment"},"activateGUI":{"type":"boolean","title":"Activate GUI","default":false,"description":"Enable or disable graphical user interface"},"simulationName":{"type":"string","title":"Simulation Name","description":"Name identifier for the simulation"},"simulationType":{"enum":["basic"],"type":"string","title":"Simulation Type","description":"Type of simulation to run"},"restoreCheckpoint":{"type":"boolean","title":"Restore Checkpoint","default":false,"description":"Enable restoring from a previously saved checkpoint snapshot"},"stepsRandomRebound":{"type":"integer","title":"Steps Random Rebound","description":"Number of steps to simulate random rebound of molecules"},"saveSimulationEvery":{"type":"integer","title":"Save Simulation Every","description":"Frequency of simulation checkpoints (in steps)"}},"description":"General configuration for the simulation"}},"description":"Configuration schema for simulation parameters"}');


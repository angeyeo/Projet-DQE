"""
Génère un fichier IFC minimal (grille 3x2 poteaux, 2 niveaux) pour
tester importer_plan/ à la main sans attendre le vrai fichier du
technicien.

Usage :
    python generer_ifc_demo.py
    -> écrit plan_demo.ifc dans le dossier courant
"""

import ifcopenshell
import ifcopenshell.api

run = ifcopenshell.api.run


def generer(xs=(0.0, 5.0, 10.0), ys=(0.0, 4.0), elevations=(0.0, 3.0)):
    model = ifcopenshell.file(schema="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="Demo")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "METERS"})

    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="Bâtiment")
    run("aggregate.assign_object", model, relating_object=project, products=[site])
    run("aggregate.assign_object", model, relating_object=site, products=[building])

    storeys = []
    for i, elev in enumerate(elevations):
        storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name=f"Niveau {i}")
        storey.Elevation = elev
        run("aggregate.assign_object", model, relating_object=building, products=[storey])
        storeys.append(storey)

    for xi, x in enumerate(xs):
        for yi, y in enumerate(ys):
            col = run("root.create_entity", model, ifc_class="IfcColumn", name=f"Poteau_{xi}_{yi}")
            run(
                "geometry.edit_object_placement", model, product=col,
                matrix=[[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, 0], [0, 0, 0, 1]],
            )
            run("spatial.assign_container", model, relating_structure=storeys[0], products=[col])

    return model


if __name__ == "__main__":
    modele = generer()
    modele.write("plan_demo.ifc")
    print("Écrit : plan_demo.ifc (grille 3x2, 2 niveaux)")

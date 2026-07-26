import os
import base64
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'STEP converter service running'})

@app.route('/convert', methods=['POST'])
def convert_step():
    """Convert STEP file to triangle mesh"""
    try:
        data = request.json
        if not data or 'file' not in data:
            return jsonify({'error': 'No file provided'}), 400

        # Decode base64
        step_content = base64.b64decode(data['file'])

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.step', mode='wb') as f:
            f.write(step_content)
            temp_path = f.name

        try:
            from OCP.STEPControl import STEPControl_Reader
            from OCP.BRepMesh import BRepMesh_IncrementalMesh
            from OCP.TopExp import TopExp_Explorer
            from OCP.TopAbs import TopAbs_FACE
            from OCP.BRep import BRep_Tool
            from OCP.TopLoc import TopLoc_Location

            # Read STEP
            reader = STEPControl_Reader()
            status = reader.ReadFile(temp_path)

            if status != 1:
                os.unlink(temp_path)
                return jsonify({'error': 'Failed to read STEP file'}), 400

            reader.TransferRoots()
            shape = reader.OneShape()

            # Mesh
            mesh = BRepMesh_IncrementalMesh(shape, 0.05, False, 0.5, True)
            mesh.Perform()

            # Extract triangles
            vertices = []
            triangles = []
            vertex_offset = 0

            explorer = TopExp_Explorer(shape, TopAbs_FACE)
            while explorer.More():
                face = explorer.Current()
                location = TopLoc_Location()
                triangulation = BRep_Tool.Triangulation_s(face, location)

                if triangulation:
                    nb_nodes = triangulation.NbNodes()
                    for i in range(1, nb_nodes + 1):
                        pnt = triangulation.Node(i)
                        if not location.IsIdentity():
                            pnt = pnt.Transformed(location.Transformation())
                        vertices.append([
                            round(float(pnt.X()), 6),
                            round(float(pnt.Y()), 6),
                            round(float(pnt.Z()), 6)
                        ])

                    nb_tris = triangulation.NbTriangles()
                    for i in range(1, nb_tris + 1):
                        tri = triangulation.Triangle(i)
                        i1, i2, i3 = tri.Get()
                        triangles.append([
                            i1 - 1 + vertex_offset,
                            i2 - 1 + vertex_offset,
                            i3 - 1 + vertex_offset
                        ])

                    vertex_offset += nb_nodes

                explorer.Next()

            os.unlink(temp_path)

            result = {
                'success': True,
                'vertices': vertices,
                'triangles': triangles,
                'vertexCount': len(vertices),
                'triangleCount': len(triangles)
            }

            print(f'Converted: {len(vertices)} vertices, {len(triangles)} triangles')
            return jsonify(result)

        except ImportError as e:
            os.unlink(temp_path)
            print(f'OCP import error: {e}')
            return jsonify({'error': 'OCP library not available'}), 500

    except Exception as e:
        print(f'Error: {str(e)}')
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

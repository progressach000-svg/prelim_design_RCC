import math
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


# ======================= SHARED HELPERS =======================
def round_up_25(x):
    return math.ceil(x / 25.0) * 25


def num(data, key, default=None, positive=True):
    raw = data.get(key)
    if raw is None or str(raw).strip() == '':
        if default is None:
            raise ValueError(f'Missing value for "{key}"')
        return float(default)
    value = float(raw)
    if positive and value <= 0:
        raise ValueError(f'"{key}" must be greater than zero')
    if not positive and value < 0:
        raise ValueError(f'"{key}" cannot be negative')
    return value


@app.route('/')
def index():
    return render_template('index.html')


# ======================= SLAB PRELIMINARY DESIGN =======================
@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        L = float(data.get('L'))
        B = float(data.get('B'))
        support = data.get('support')
        c = float(data.get('c', 15))
        phi = float(data.get('phi'))

        # Step 2: Determine Span-to-Depth Ratio (L/d Criteria)
        # Find max and min spans
        L_max = max(L, B)
        L_min = min(L, B)
        L_short = L_min

        # Check slab type
        ratio = round(L_max / L_min, 2)
        slab_type = f'1-way (Ly/Lx = {ratio})' if ratio >= 2 else f'2-way (Ly/Lx = {ratio})'

        X = 25 if support == 'SS' else 32

        # Step 3: Calculate the minimum effective depth
        d_min = L_short / X

        # Step 4: Compute total depth
        D_calc = d_min + c + (phi / 2.0)

        # Step 5: Check Sizing Constraints & Iterate
        if D_calc > 150:
            status = 'revise'
            message = 'The slab is relatively thick. Consider adding a secondary beam to reduce the effective span (L), then repeat from Step 1.'
            D_final = D_calc
            d_final = d_min
        else:
            status = 'success'
            message = 'Slab thickness is within optimal limits (≤ 150 mm).'
            # Round up D to the nearest higher multiple of 25 mm
            D_final = math.ceil(D_calc / 25.0) * 25
            # Recalculate effective depth with the final D
            d_final = D_final - c - (phi / 2.0)

        return jsonify({
            'status': status,
            'message': message,
            'slab_type': slab_type,
            'L_short': L_short,
            'X': X,
            'd_min': round(d_min, 2),
            'D_calc': round(D_calc, 2),
            'D_final': round(D_final, 2),
            'd_final': round(d_final, 2),
            'c': c,
            'phi': phi
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ======================= BEAM PRELIMINARY DESIGN =======================
# Allowed ranges for the proportioning ratios (defaults are the mid-range values)
SPAN_DEPTH_RANGE = (10.0, 15.0)    # default 12
DEPTH_WIDTH_RANGE = (1.5, 2.5)     # default 2.0

# Moment factor X by steel grade
MOMENT_FACTOR = {500: 0.1336, 415: 0.138, 250: 0.148}


@app.route('/calculate_beam', methods=['POST'])
def calculate_beam():
    try:
        data = request.json

        # ---- Inputs ----
        lb = num(data, 'lb')
        Ab = num(data, 'Ab')
        Ds = num(data, 'Ds')
        lw = num(data, 'lw', 0, positive=False)
        bw = num(data, 'bw', 0, positive=False)
        tw = num(data, 'tw', 0, positive=False)

        gamma_c = num(data, 'gamma_c', 25)
        gamma_w = num(data, 'gamma_w', 20)
        LL = num(data, 'LL', 0, positive=False)
        FL = num(data, 'FL', 0, positive=False)
        eta = num(data, 'eta', 1.0)

        fck = num(data, 'fck')
        fy = int(float(data.get('fy')))
        support = data.get('support')
        d_dash = num(data, 'd_dash', 40)

        ratio_span_depth = num(data, 'ratio_span_depth', 12)
        ratio_depth_width = num(data, 'ratio_depth_width', 2.0)

        if fy not in MOMENT_FACTOR:
            raise ValueError('Steel grade fy must be 250, 415 or 500 N/mm²')
        if support not in ('SS', 'Cont'):
            raise ValueError('Invalid support condition')
        if not (SPAN_DEPTH_RANGE[0] <= ratio_span_depth <= SPAN_DEPTH_RANGE[1]):
            raise ValueError('Span/depth ratio must be between 10 and 15')
        if not (DEPTH_WIDTH_RANGE[0] <= ratio_depth_width <= DEPTH_WIDTH_RANGE[1]):
            raise ValueError('Depth/width ratio must be between 1.5 and 2.5')

        # ---- Step 2: Initial geometric estimation ----
        d_trial = lb * 1000 / ratio_span_depth
        b_raw = d_trial / ratio_depth_width
        b_trial = round_up_25(b_raw)
        D_raw = d_trial + d_dash
        D_trial = round_up_25(D_raw)
        d_est = D_trial - d_dash

        # ---- Step 3: Service load ----
        W_slab = Ab * Ds * gamma_c
        W_LL = LL * Ab
        W_FL = FL * Ab
        W_beam = lb * (D_trial / 1000) * (b_trial / 1000) * gamma_c
        W_wall = lw * bw * tw * gamma_w * eta
        W = W_slab + W_LL + W_FL + W_beam + W_wall

        # ---- Step 4: UDL and maximum bending moment ----
        w = W / lb
        M_max = (w * lb ** 2 / 10) if support == 'Cont' else (w * lb ** 2 / 8)

        # ---- Step 5: Moment capacity check ----
        X = MOMENT_FACTOR[fy]
        d_req = math.sqrt(M_max * 1e6 / (X * b_trial * fck))
        D_req = d_req + d_dash

        # ---- Step 6: Final section selection ----
        D_gov = max(D_trial, D_req)
        D_final = round_up_25(D_gov)
        d_final = D_final - d_dash
        b_final = b_trial

        if D_req <= D_trial:
            status = 'success'
            message = 'Deflection criterion governs. The trial section is adequate for flexure.'
        else:
            status = 'revise'
            message = 'Flexure (moment capacity) governs. The depth has been increased beyond the trial depth.'

        r = lambda v: round(v, 2)
        return jsonify({
            'status': status,
            'message': message,
            'lb': lb,
            'd_dash': d_dash,
            'ratio_span_depth': ratio_span_depth,
            'ratio_depth_width': ratio_depth_width,
            'd_trial': r(d_trial),
            'b_raw': r(b_raw),
            'D_raw': r(D_raw),
            'b_trial': b_trial,
            'D_trial': D_trial,
            'd_est': r(d_est),
            'W_slab': r(W_slab), 'W_LL': r(W_LL), 'W_FL': r(W_FL),
            'W_beam': r(W_beam), 'W_wall': r(W_wall),
            'W': r(W),
            'w': r(w),
            'M_max': r(M_max),
            'X': X,
            'd_req': r(d_req),
            'D_req': r(D_req),
            'D_gov': r(D_gov),
            'b_final': b_final,
            'D_final': D_final,
            'd_final': r(d_final),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ======================= COLUMN PRELIMINARY SIZING =======================
SEISMIC_RANGE = (1.25, 1.30)     # default 1.30
STEEL_PCT_RANGE = (0.8, 4.0)     # IS 456: min 0.8 %, practical max 4 % (default 1 %)
ASPECT_RANGE = (1.0, 3.0)        # D/b for rectangular columns (default 1.5)


@app.route('/calculate_column', methods=['POST'])
def calculate_column():
    try:
        data = request.json

        # ---- Inputs ----
        Ac = num(data, 'Ac')
        N = num(data, 'N_storey')
        Ds = num(data, 'Ds')
        lbc = num(data, 'lbc', 0, positive=False)
        bb = num(data, 'bb', 0, positive=False)
        Db = num(data, 'Db', 0, positive=False)
        lw = num(data, 'lw', 0, positive=False)
        bw = num(data, 'bw', 0, positive=False)
        tw = num(data, 'tw', 0, positive=False)

        gamma_c = num(data, 'gamma_c', 25)
        gamma_w = num(data, 'gamma_w', 20)
        LL = num(data, 'LL', 0, positive=False)
        FL = num(data, 'FL', 0, positive=False)
        eta = num(data, 'eta', 1.0)
        K = num(data, 'K_seismic', 1.30)

        fck = num(data, 'fck')
        fy = num(data, 'fy')
        p_steel = num(data, 'p_steel', 1.0)          # in percent
        section = data.get('section_type')
        aspect = num(data, 'aspect_r', 1.5)

        if N != int(N):
            raise ValueError('Number of storeys must be a whole number')
        if section not in ('Square', 'Rectangular'):
            raise ValueError('Invalid column section type')
        if not (SEISMIC_RANGE[0] <= K <= SEISMIC_RANGE[1]):
            raise ValueError('Seismic factor must be between 1.25 and 1.30')
        if not (STEEL_PCT_RANGE[0] <= p_steel <= STEEL_PCT_RANGE[1]):
            raise ValueError('Steel percentage must be between 0.8 and 4 %')
        if section == 'Rectangular' and not (ASPECT_RANGE[0] <= aspect <= ASPECT_RANGE[1]):
            raise ValueError('Aspect ratio D/b must be between 1.0 and 3.0')
        if Db > 0 and Db <= Ds:
            raise ValueError('Beam overall depth must be greater than slab thickness')

        # ---- Step 2: Single-floor gravity load ----
        W_slab = Ac * Ds * gamma_c + LL * Ac + FL * Ac
        W_beam = lbc * max(Db - Ds, 0) * bb * gamma_c
        W_wall = lw * bw * tw * gamma_w * eta
        W_floor = W_slab + W_beam + W_wall

        # ---- Step 3: Ultimate load with seismic amplification ----
        W_total = W_floor * N
        Pu = 1.5 * W_total * K

        # ---- Step 4: Gross area (IS 456 cl. 39.3, short column) ----
        p = p_steel / 100.0
        denom = 0.4 * fck * (1 - p) + 0.67 * fy * p
        A_gross = Pu * 1e3 / denom

        # ---- Step 5: Dimensions and rounding ----
        if section == 'Square':
            b_calc = math.sqrt(A_gross)
            D_calc = b_calc
        else:
            b_calc = math.sqrt(A_gross / aspect)
            D_calc = b_calc * aspect
        b_final = round_up_25(b_calc)
        D_final = round_up_25(D_calc)
        A_provided = b_final * D_final
        A_steel_final = p * A_provided

        r = lambda v: round(v, 2)
        return jsonify({
            'section_type': section,
            'message': ('Square column adopted.' if section == 'Square'
                        else f'Rectangular column adopted with D/b = {aspect:g}.'),
            'W_slab': r(W_slab), 'W_beam': r(W_beam), 'W_wall': r(W_wall),
            'W_floor': r(W_floor), 'W_total': r(W_total),
            'K_seismic': K, 'Pu': r(Pu),
            'p_steel': p_steel, 'A_gross': r(A_gross),
            'b_calc': r(b_calc), 'D_calc': r(D_calc),
            'b_final': b_final, 'D_final': D_final,
            'A_provided': r(A_provided), 'A_steel_final': r(A_steel_final),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, port=5000)

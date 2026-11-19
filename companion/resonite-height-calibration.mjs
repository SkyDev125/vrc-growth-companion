/** One-time avatar authoring helper. The desktop companion does not need ResoniteLink. */
import { parseArgs } from 'node:util';
import { pathToFileURL } from 'node:url';

const avatarRootType = '[FrooxEngine]FrooxEngine.CommonAvatar.AvatarRoot';
const userRootType = '[FrooxEngine]FrooxEngine.UserRoot';
const vrikType = '[FrooxEngine]FrooxEngine.FinalIK.VRIKAvatar';
const referenceTag = 'midsden/rig-eye-height';
const referenceType = /^\[FrooxEngine\]FrooxEngine\.ValueField<(?:\[[^\]]+\])?System\.Single>$/;

class Unavailable extends Error {}

function positive(value) {
    return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

function vector(field, axes) {
    const values = axes.map(axis => field?.value?.[axis]);
    if (!values.every(Number.isFinite)) throw new Unavailable('A required slot transform is unavailable.');
    return values;
}

function cross([x, y, z], [a, b, c]) {
    return [y * c - z * b, z * a - x * c, x * b - y * a];
}

function transformPoint(slot, point) {
    const scale = vector(slot.scale, ['x', 'y', 'z']);
    if (!scale.every(positive)) throw new Unavailable('A model or marker slot has a zero or mirrored scale.');
    const position = vector(slot.position, ['x', 'y', 'z']);
    const rotation = vector(slot.rotation, ['x', 'y', 'z', 'w']);
    const norm = Math.hypot(...rotation);
    if (!positive(norm)) throw new Unavailable('A model or marker slot has an invalid rotation.');
    const q = rotation.map(value => value / norm);
    const scaled = point.map((value, axis) => value * scale[axis]);
    const t = cross(q, scaled).map(value => value * 2);
    const correction = cross(q, t);
    return scaled.map((value, axis) => value + q[3] * t[axis] + correction[axis] + position[axis]);
}

function inUserSpace(chain, point) {
    return chain.reduce((current, slot) => transformPoint(slot, current), point);
}

function componentOfType(slot, type) {
    return slot.components?.filter(component => component.componentType === type) ?? [];
}

async function getSlot(request, slotId) {
    const response = await request({ $type: 'getSlot', slotId, depth: 0, includeComponentData: true });
    if (!response.data || response.data.isReferenceOnly || response.data.id !== slotId) {
        throw new Error(`ResoniteLink did not return the requested slot ${slotId}.`);
    }
    return response.data;
}

async function chainTo(request, start, stop) {
    const chain = [];
    const seen = new Set();
    let current = start;
    while (current) {
        if (stop(current)) return { chain, root: current };
        if (seen.has(current.id) || chain.length >= 64) throw new Unavailable('The avatar hierarchy could not be resolved.');
        seen.add(current.id);
        chain.push(current);
        const parent = current.parent?.targetId;
        if (!parent || parent === 'Root') break;
        current = await getSlot(request, parent);
    }
    throw new Unavailable('That slot does not belong to the expected avatar or wearer.');
}

async function authoredHeight(request, avatar, modelChain, eyeSlot, floorSlot) {
    const toUser = async id => {
        const marker = await getSlot(request, id);
        const { chain } = await chainTo(request, marker, slot => slot.id === avatar.id);
        return inUserSpace([...chain, ...modelChain], [0, 0, 0])[1];
    };
    return await toUser(eyeSlot) - await toUser(floorSlot);
}

/** Validates rig-local AvatarHeight against authored eye/floor markers before it can be applied. */
export async function calibrate(request, { avatarSlot, eyeSlot, floorSlot, referenceSlot, apply = false }) {
    if (Boolean(eyeSlot) !== Boolean(floorSlot)) throw new Error('Supply both the eye and floor marker slots.');
    if (apply && !(eyeSlot && floorSlot && referenceSlot)) {
        throw new Error('Applying needs both authored markers and the dedicated rig reference slot.');
    }
    try {
        const avatar = await getSlot(request, avatarSlot);
        const roots = componentOfType(avatar, avatarRootType).filter(root => root.members?.Enabled?.value !== false);
        const rigs = componentOfType(avatar, vrikType).filter(rig => rig.members?.Enabled?.value !== false);
        if (roots.length !== 1 || rigs.length !== 1) {
            throw new Unavailable('The selected avatar root has no single enabled VRIKAvatar.');
        }
        const rig = rigs[0];
        const height = rig.members?.AvatarHeight?.value;
        if (!positive(height)) throw new Unavailable('The rig has no usable AvatarHeight.');
        const { chain, root } = await chainTo(request, avatar, slot => componentOfType(slot, userRootType).length === 1);
        const floor = inUserSpace(chain, [0, 0, 0])[1];
        const candidate = inUserSpace(chain, [0, height, 0])[1] - floor;
        if (!positive(Math.fround(candidate))) throw new Unavailable('The rig has no usable upright height in wearer space.');

        const result = {
            source: 'vrik-candidate', wearerRoot: root.id, avatarHeight: height,
            heightCompensation: rig.members?.HeightCompensation?.value ?? null,
            referenceMetres: candidate, verified: false,
        };
        if (!eyeSlot) return result;
        const authored = await authoredHeight(request, avatar, chain, eyeSlot, floorSlot);
        if (!positive(authored) || Math.abs(authored - candidate) / authored > 0.02) {
            return { ...result, source: 'standing-capture', authoredReferenceMetres: authored,
                reason: 'The rig-local height disagrees with the authored markers. Use the standing capture.' };
        }
        result.verified = true;
        result.authoredReferenceMetres = authored;
        if (!apply) return result;

        const dest = await getSlot(request, referenceSlot);
        const { chain: destinationChain } = await chainTo(request, dest, slot => slot.id === avatar.id);
        const fields = dest.components?.filter(component => referenceType.test(component.componentType)) ?? [];
        if (!destinationChain.length || dest.tag?.value !== referenceTag || fields.length !== 1
            || fields[0].members?.Value?.$type !== 'float') {
            throw new Error(`Choose a dedicated child tagged ${referenceTag} with one ValueField<float>.`);
        }
        const id = fields[0].id;
        if (!id) throw new Error('ResoniteLink did not return the reference component ID.');
        await request({ $type: 'updateComponent', data: { id, members: { Value: { $type: 'float', value: Math.fround(candidate) } } } });
        const saved = await getSlot(request, referenceSlot);
        const stored = saved.components?.find(component => component.id === id)?.members?.Value?.value;
        if (!positive(stored) || Math.fround(stored) !== Math.fround(candidate)) {
            throw new Error('The saved reference did not match on readback.');
        }
        return { ...result, applied: true };
    } catch (error) {
        if (!(error instanceof Unavailable)) throw error;
        return { source: 'standing-capture', verified: false, reason: error.message };
    }
}

function exchange(socket, message, messageId) {
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => finish(new Error('ResoniteLink did not respond within five seconds.')), 5000);
        function finish(error, value) {
            clearTimeout(timer);
            socket.removeEventListener('message', receive);
            socket.removeEventListener('close', closed);
            if (error) reject(error); else resolve(value);
        }
        function receive(event) {
            if (typeof event.data !== 'string') return;
            try {
                const response = JSON.parse(event.data);
                if (response.sourceMessageId !== messageId) return;
                if (!response.success) throw new Error(response.errorInfo || 'ResoniteLink denied the request.');
                finish(null, response);
            } catch (error) {
                finish(error);
            }
        }
        function closed() { finish(new Error('ResoniteLink disconnected.')); }
        socket.addEventListener('message', receive);
        socket.addEventListener('close', closed);
        try { socket.send(JSON.stringify({ ...message, messageId })); }
        catch (error) { finish(error); }
    });
}

async function main() {
    const { values } = parseArgs({ options: {
        port: { type: 'string' }, 'avatar-slot': { type: 'string' }, 'eye-slot': { type: 'string' },
        'floor-slot': { type: 'string' }, 'reference-slot': { type: 'string' }, apply: { type: 'boolean' },
    } });
    const port = Number(values.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535 || !values['avatar-slot']) {
        throw new Error('Use --port PORT --avatar-slot SLOT_ID. Add --eye-slot ID --floor-slot ID to verify against authored markers.');
    }
    // Only author against the explicitly enabled Link session on this computer.
    const socket = new WebSocket(`ws://127.0.0.1:${port}`);
    try {
        await new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error('Timed out opening local ResoniteLink.')), 5000);
            socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
            socket.addEventListener('error', () => {
                clearTimeout(timer);
                reject(new Error('Could not open local ResoniteLink. Check the session and port.'));
            }, { once: true });
        });
        let nextId = 0;
        const result = await calibrate(message => exchange(socket, message, String(++nextId)), {
            avatarSlot: values['avatar-slot'], eyeSlot: values['eye-slot'], floorSlot: values['floor-slot'],
            referenceSlot: values['reference-slot'], apply: values.apply,
        });
        console.log(JSON.stringify(result, null, 2));
        if (values.apply && !result.applied) process.exitCode = 1;
    } finally {
        socket.close();
    }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
